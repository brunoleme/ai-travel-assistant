"""
YouTube ingestion: fetch (yt-dlp), segment, chunk, enrich (OpenAI), write (Weaviate).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
import weaviate

from app.weaviate_schema import ensure_collections

LangCode = Literal["pt", "en", "es", "auto"]
CardCategory = Literal[
    "attraction", "food", "hotel", "transport", "shopping",
    "tip", "warning", "itinerary", "budget", "timing", "other",
]


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


_TIME = re.compile(r"(\d\d):(\d\d):(\d\d)\.(\d\d\d)")


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def vtt_to_segments(vtt_text: str) -> list[dict[str, Any]]:
    """Parse VTT content into segments with start, duration, text."""
    lines = [ln.rstrip("\n") for ln in vtt_text.splitlines()]
    segs: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_str, end_str = [x.strip() for x in line.split("-->")]
            ms = _TIME.search(start_str)
            me = _TIME.search(end_str)
            if ms and me:
                start = _to_seconds(*ms.groups())
                end = _to_seconds(*me.groups())
                i += 1
                text_lines: list[str] = []
                while i < len(lines) and lines[i].strip() != "":
                    txt = re.sub(r"<[^>]+>", "", lines[i]).strip()
                    if txt:
                        text_lines.append(txt)
                    i += 1
                text = " ".join(text_lines).strip()
                if text:
                    segs.append({"start": start, "duration": max(0.0, end - start), "text": text})
        i += 1
    return segs


def _lang_preference(lang_hint: LangCode) -> list[str]:
    if lang_hint == "auto":
        return ["pt", "pt-BR", "pt-PT", "en", "es"]
    if lang_hint == "pt":
        return ["pt", "pt-BR", "pt-PT", "en", "es"]
    return [lang_hint, "en", "es", "pt", "pt-BR", "pt-PT"]


def _ytdlp_cookie_args() -> list[str]:
    """If YTDLP_COOKIES_FILE is set and the file exists, return --cookies <path> args."""
    path = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if path and Path(path).is_file():
        return ["--cookies", path]
    return []


def get_video_metadata(video_url: str) -> dict[str, Any]:
    """Get video metadata via yt-dlp --dump-single-json."""
    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-check-formats",  # we only need metadata, not a downloadable format
        "--ignore-no-formats-error",
        "--extractor-retries", "1",
        "--socket-timeout", "10",
        *_ytdlp_cookie_args(),
        video_url,
    ]
    out = subprocess.check_output(cmd, text=True, timeout=30)
    return json.loads(out)


def fetch_subtitles_via_ytdlp(video_url: str, lang_hint: LangCode) -> tuple[list[dict[str, Any]], str]:
    """Fetch VTT subtitles and parse to segments. Returns (segments, chosen_lang)."""
    langs = _lang_preference(lang_hint)
    with tempfile.TemporaryDirectory() as td:
        for lang in langs:
            for f in Path(td).glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-subs",
                "--write-subs",
                "--sub-langs", lang,
                "--sub-format", "vtt",
                "--no-check-formats",
                "--ignore-no-formats-error",
                "-o", str(Path(td) / "%(id)s.%(ext)s"),
                *_ytdlp_cookie_args(),
                video_url,
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            except subprocess.CalledProcessError:
                continue
            vtts = list(Path(td).glob("*.vtt"))
            if not vtts:
                continue
            vtt_text = vtts[0].read_text(encoding="utf-8", errors="ignore")
            segs = vtt_to_segments(vtt_text)
            if segs:
                return segs, lang
    raise RuntimeError("No subtitles available via yt-dlp for preferred languages.")


def fetch_youtube_transcript(
    video_url: str,
    language_hint: LangCode = "auto",
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """
    Fetch metadata and subtitles for one video.
    Returns (segments, chosen_lang, video_metadata).
    video_metadata: id, title, channel, upload_date, webpage_url (for Weaviate).
    """
    meta = get_video_metadata(video_url)
    segments, chosen_lang = fetch_subtitles_via_ytdlp(video_url, language_hint)
    video_id = meta.get("id") or _extract_video_id(meta.get("webpage_url", "")) or ""
    webpage_url = meta.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
    upload_date = _parse_upload_date(meta)
    video_metadata = {
        "id": video_id,
        "title": meta.get("title") or "",
        "channel": meta.get("channel") or meta.get("uploader") or "",
        "upload_date": upload_date,
        "webpage_url": webpage_url,
    }
    return segments, chosen_lang, video_metadata


def _parse_upload_date(meta: dict[str, Any]) -> str | None:
    ud = meta.get("upload_date")
    if isinstance(ud, str) and re.fullmatch(r"\d{8}", ud):
        dt = datetime.strptime(ud, "%Y%m%d").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    ts = meta.get("timestamp")
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    return None


_BOUNDARY_CUES = [
    r"\bagora\b", r"\bpr[oó]xima dica\b", r"\boutro ponto\b", r"\bmudando de assunto\b",
    r"\bvamos falar de\b", r"\bsobre (compras|parques|praias|hotel|comida|transporte)\b",
    r"\bnow\b", r"\bnext tip\b", r"\bmoving on\b", r"\blet's talk about\b",
    r"\bahora\b", r"\bsiguiente consejo\b", r"\bcambiando de tema\b", r"\bvamos a hablar de\b",
]
_BOUNDARY_RE = re.compile("|".join(_BOUNDARY_CUES), re.IGNORECASE)


def chunk_timestamped_segments(
    segments: list[dict[str, Any]],
    *,
    max_chars: int = 1200,
    min_chars: int = 350,
    max_duration_s: int = 75,
    min_duration_s: int = 25,
    gap_split_s: float = 2.5,
) -> list[dict[str, Any]]:
    """Chunk segments into {startSec, endSec, text} list."""
    norm: list[tuple[float, float, str]] = []
    for s in segments:
        start = float(s["start"])
        dur = float(s.get("duration", 0.0))
        end = start + dur
        txt = (s.get("text") or "").strip()
        if txt:
            norm.append((start, end, txt))
    chunks: list[dict[str, Any]] = []
    cur: list[tuple[float, float, str]] = []

    def flush() -> None:
        nonlocal cur
        if not cur:
            return
        text = " ".join(t for _, _, t in cur).strip()
        chunks.append({"startSec": int(cur[0][0]), "endSec": int(cur[-1][1]), "text": text})
        cur.clear()

    def cur_stats() -> tuple[int, float]:
        if not cur:
            return 0, 0.0
        text = " ".join(t for _, _, t in cur).strip()
        duration = cur[-1][1] - cur[0][0]
        return len(text), duration

    for (start, end, txt) in norm:
        if cur:
            prev_end = cur[-1][1]
            if (start - prev_end) > gap_split_s:
                flush()
        cur.append((start, end, txt))
        n_chars, dur = cur_stats()
        tail = " ".join(t for _, _, t in cur[-2:]) if len(cur) >= 2 else cur[-1][2]
        boundary = bool(_BOUNDARY_RE.search(tail))
        if (n_chars >= max_chars) or (dur >= max_duration_s) or (
            boundary and n_chars >= min_chars and dur >= min_duration_s
        ):
            flush()
    flush()
    return chunks


class RecommendationCard(BaseModel):
    """Travel recommendation card from a chunk."""
    summary: str = Field(min_length=10)
    primaryCategory: CardCategory = "other"
    categories: list[CardCategory] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str | None = None


def _fallback_card(chunk_text: str) -> RecommendationCard:
    s = re.sub(r"\s+", " ", chunk_text).strip()
    s = s[:240] if len(s) > 240 else s
    if len(s) < 10:
        s = "Trecho curto sem resumo confiável."
    return RecommendationCard(
        summary=s,
        primaryCategory="other",
        categories=["other"],
        places=[],
        signals=[],
        confidence=0.2,
        rationale="Fallback: chunk too weak/failed to parse.",
    )


def enrich_chunk_to_card(
    *,
    chunk_text: str,
    destination: str,
    source_lang: str,
    model: str = "gpt-4.1-mini",
) -> RecommendationCard:
    """Enrich one chunk to a RecommendationCard via OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required for enrich.")
    client = OpenAI(api_key=api_key)
    system = """You extract travel recommendation cards from transcript chunks.
Return ONLY valid JSON. No markdown. No extra text.
SUMMARY: 1–3 sentences, at least 20 characters.
PLACES: only proper nouns. SIGNALS: actionable travel tactics, no CTAs.
CATEGORIES: primaryCategory one of attraction,food,hotel,transport,shopping,tip,warning,itinerary,budget,timing,other; categories 1–6.
CONFIDENCE: 0–1. If signals empty, confidence <= 0.4 and primaryCategory other.
RATIONALE: one short sentence. Output in same language as transcript."""
    payload = {"destination": destination, "source_lang": source_lang, "chunk_text": chunk_text}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            return _fallback_card(chunk_text)
        data = json.loads(m.group(0))
    except Exception:
        return _fallback_card(chunk_text)
    if not isinstance(data.get("summary"), str) or len((data["summary"] or "").strip()) < 20:
        data["summary"] = re.sub(r"\s+", " ", chunk_text).strip()[:240] or "Resumo indisponível."
    data.setdefault("places", [])
    data.setdefault("signals", [])
    data.setdefault("categories", [])
    data["primaryCategory"] = data.get("primaryCategory") or "other"
    if data["primaryCategory"] not in data["categories"]:
        data["categories"] = [data["primaryCategory"]] + [c for c in data["categories"] if c != data["primaryCategory"]]
    data["categories"] = data["categories"][:6]
    data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.4))))
    if not data["signals"]:
        data["confidence"] = min(data["confidence"], 0.4)
        data["primaryCategory"] = "other"
        data["categories"] = ["other"]
    try:
        return RecommendationCard(**data)
    except ValidationError:
        return _fallback_card(chunk_text)


def make_timestamp_url(video_url: str, start_sec: int) -> str:
    return f"{video_url}&t={start_sec}s"


def stable_uuid_for_video(video_url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, video_url))


def stable_uuid_for_card(video_uuid: str, start_sec: int, end_sec: int, text: str) -> str:
    import hashlib
    h = hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()[:10]
    key = f"{video_uuid}:{start_sec}:{end_sec}:{h}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _connect_weaviate() -> weaviate.WeaviateClient:
    host = os.environ.get("WEAVIATE_HOST", "localhost")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))
    grpc_port = int(os.environ.get("WEAVIATE_GRPC_PORT", "50051"))
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=port,
        http_secure=False,
        grpc_host=host,
        grpc_port=grpc_port,
        grpc_secure=False,
        skip_init_checks=True,
    )


def write_youtube_to_weaviate(
    video_metadata: dict[str, Any],
    chunks: list[dict[str, Any]],
    cards: list[RecommendationCard],
    *,
    destination: str = "",
    playlist_url: str = "",
    playlist_name: str = "",
    creator_tier: str = "",
    lang: str = "pt",
) -> None:
    """Upsert Video and insert RecommendationCards. Ensures schema first."""
    ensure_collections()
    client = _connect_weaviate()
    try:
        videos = client.collections.use("Video")
        video_id = video_metadata.get("id", "")
        video_url = video_metadata.get("webpage_url", "")
        vid_uuid = stable_uuid_for_video(video_url)
        if not videos.data.exists(vid_uuid):
            props: dict[str, Any] = {
                "videoId": str(video_id),
                "videoUrl": str(video_url),
                "title": str(video_metadata.get("title", "")),
                "channel": str(video_metadata.get("channel", "")),
                "lang": lang,
                "playlistUrl": playlist_url,
                "playlistName": playlist_name,
                "creatorTier": creator_tier,
            }
            if video_metadata.get("upload_date"):
                props["uploadDate"] = video_metadata["upload_date"]
            videos.data.insert(uuid=vid_uuid, properties=props)
        cards_coll = client.collections.use("RecommendationCard")
        video_upload_date = video_metadata.get("upload_date")
        for i, (chunk, card) in enumerate(zip(chunks, cards)):
            start_sec = chunk.get("startSec", 0)
            end_sec = chunk.get("endSec", 0)
            text = chunk.get("text", "")
            card_uuid = stable_uuid_for_card(vid_uuid, start_sec, end_sec, text)
            if cards_coll.data.exists(card_uuid):
                continue
            timestamp_url = make_timestamp_url(video_url, start_sec)
            props_card: dict[str, Any] = {
                "summary": card.summary,
                "text": text,
                "startSec": float(start_sec),
                "endSec": float(end_sec),
                "timestampUrl": timestamp_url,
                "lang": lang,
                "destination": destination,
                "categories": card.categories,
                "primaryCategory": card.primaryCategory,
                "places": card.places,
                "signals": card.signals,
                "confidence": float(card.confidence),
                "rationale": card.rationale or "",
            }
            if video_upload_date:
                props_card["videoUploadDate"] = video_upload_date
            cards_coll.data.insert(
                uuid=card_uuid,
                properties=props_card,
                references={"fromVideo": vid_uuid},
            )
    finally:
        client.close()
