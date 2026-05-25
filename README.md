# FEDDAKALKUN Venice Agent Studio

Venice API desktop-style Gradio app with:
- Agent-style chat (history, system prompt, character slug, web search mode)
- Live text/image model refresh from `/models`
- Image generation via `/image/generate`
- Chroma model filter helper for image models containing `chroma`
- Local history/gallery and prompt template helpers

## Setup

1. Run `Install-FEDDAKALKUN-Venice-Agent-Studio.bat`
2. Run `Run-FEDDAKALKUN-Venice-Agent-Studio.bat`
3. Paste your Venice API key in the app settings and save locally

## Single-file install

You can share only this file:

`FEDDAKALKUN-Venice-Agent-Studio-OneClick-Install.bat`

It downloads the latest app from GitHub, installs requirements, and leaves the user with the normal run/update BAT files.

## Updates

If this app was installed from a git repository, run:

`Update-FEDDAKALKUN-Venice-Agent-Studio.bat`

The updater pulls the latest app files and refreshes Python requirements.

Recommended install source:

`git clone https://github.com/Feddakalkun/fedda-venice-api.git FEDDAKALKUN-Venice-Agent-Studio`

## Notes

- Uses Venice API base URL: `https://api.venice.ai/api/v1`
- Local config is saved to `.venice_config.json` in this app folder
- `.venice_config.json`, `outputs/`, `.venv/`, and prompt libraries are ignored by git
- API availability/pricing can change during beta periods
