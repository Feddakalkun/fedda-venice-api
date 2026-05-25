# FEDDAKALKUN Venice Agent Studio

## Purpose
Provide a FEDDAKALKUN-branded Gradio app for Venice API chat + image generation workflows.

## Target user
Users who want Venice agent-style chat and image generation from one local UI.

## Core behavior
- Authenticate with Venice API key.
- Discover chat/image models dynamically from Venice `/models`.
- Run conversational chat with stateful message history.
- Generate images via Venice `/image/generate`.
- Filter image models by `chroma` keyword.

## User flow
1. Open app and paste API key.
2. Refresh models and choose chat/image models.
3. Chat in Agent tab with optional character and web search settings.
4. Generate image in Image tab.

## Inputs
- API key
- Chat model / image model
- Prompt / negative prompt
- Chat controls: system prompt, character slug, web search, temperature, max tokens
- Image controls: width, height, steps, cfg, variants, seed, safe mode

## Outputs
- Chat responses + token/time status
- Generated image + timing status

## Notes
- API endpoint defaults align with Venice docs.
- Chat and image requests use separate Venice endpoints.
