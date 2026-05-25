# Log

## 2026-05-25
- Created new app scaffold: `FEDDAKALKUN-Venice-Agent-Studio`.
- Implemented Venice API chat integration via `/chat/completions`.
- Implemented Venice image generation integration via `/image/generate`.
- Added model discovery via `/models?type=text` and `/models?type=image`.
- Added Chroma model filter helper for image model selection.
- Added install/run BAT workflow and local config save.
- Added account/credits view, autosave history, prompt templates, and gallery.
- Removed experimental image edit tabs from the shareable beta until Venice model IDs/payloads are verified.
- Added git-based updater BAT and gitignore for local API keys, outputs, venv, and user prompt libraries.
