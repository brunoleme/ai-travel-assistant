# Vision test images

Images here are used by **mcp-travel-vision** (and later **agent-api**) for optional real-image tests.

**Filename convention** (prefix → analysis mode):

| Prefix      | Mode               |
|------------|--------------------|
| `outfit_*` | packing            |
| `landmark_*` | landmark         |
| `product_*` | product_similarity |

Tests run only when `OPENAI_API_KEY` is set and skip otherwise.
