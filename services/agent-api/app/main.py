from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="ai-travel-assistant agent-api", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            # Minimal contract for Phase 1:
            # echo user_query back as answer_text
            user_query = msg.get("user_query", "")
            session_id = msg.get("session_id") or "local-session"
            request_id = msg.get("request_id") or "local-request"

            await ws.send_json(
                {
                    "session_id": session_id,
                    "request_id": request_id,
                    "answer_text": f"echo: {user_query}",
                    "citations": [],
                    "addon": None,
                }
            )
    except WebSocketDisconnect:
        return
