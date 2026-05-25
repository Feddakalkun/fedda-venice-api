import base64
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import gradio as gr
from PIL import Image


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / ".venice_config.json"
API_BASE = "https://api.venice.ai/api/v1"
OUTPUTS_DIR = APP_DIR / "outputs"
PROMPT_LIBRARY_PATH = APP_DIR / "prompt_library.json"
IMAGE_HISTORY_PATH = OUTPUTS_DIR / "image_history.jsonl"
DEFAULT_CHAT_MODEL = "zai-org-glm-5-1"
DEFAULT_IMAGE_MODEL = "chroma"
PREFERRED_CHAT_MODELS = [
    "zai-org-glm-5-1",
    "zai-org-glm-5",
    "z-ai-glm-5-turbo",
    "qwen-3-235b",
    "qwen-3-30b",
    "venice-uncensored-r1",
    "venice-uncensored-roleplay",
    "llama",
    "mistral",
    "gemma",
]
PREFERRED_IMAGE_MODELS = [
    "chroma",
    "venice-sd35",
    "fluently-xl-final",
    "flux",
    "hidream",
    "stable-diffusion",
    "sdxl",
]
IMAGE_INTENT_WORDS = [
    "generate image",
    "generate an image",
    "make image",
    "make an image",
    "create image",
    "create an image",
    "draw",
    "picture",
    "photo",
    "illustration",
    "render",
    "visualize",
    "text to image",
    "txt2img",
]

APP_CSS = """
:root {
  --fk-bg: #0b0b0d;
  --fk-panel: #18191d;
  --fk-panel-2: #222329;
  --fk-border: #343741;
  --fk-text: #f4f4f5;
  --fk-muted: #b7bbc7;
  --fk-orange: #ff6a00;
  --fk-green: #2fd36b;
}
.gradio-container {
  max-width: 1480px !important;
  margin: 0 auto !important;
  background: var(--fk-bg) !important;
}
.fk-hero {
  border: 1px solid var(--fk-border);
  border-radius: 8px;
  padding: 18px 20px;
  margin-bottom: 14px;
  background: linear-gradient(135deg, #17191f 0%, #23272e 72%, #2e251d 100%);
}
.fk-kicker {
  color: var(--fk-orange);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.fk-hero h1 {
  margin: 6px 0 4px 0;
  font-size: 30px;
  line-height: 1.15;
}
.fk-hero p {
  margin: 0;
  color: var(--fk-muted);
  max-width: 860px;
}
.fk-statusbar {
  border: 1px solid var(--fk-border);
  background: var(--fk-panel);
  border-radius: 8px;
  padding: 10px 12px;
  margin: 8px 0 14px 0;
}
.fk-statusbar p {
  margin: 0 !important;
}
.fk-workspace {
  align-items: stretch;
}
.fk-left, .fk-right {
  border: 1px solid var(--fk-border);
  border-radius: 8px;
  background: var(--fk-panel);
  padding: 12px;
}
.fk-output img {
  object-fit: contain !important;
}
button.primary, .primary > button {
  background: var(--fk-orange) !important;
  border-color: var(--fk-orange) !important;
}
textarea, input, .wrap, .input-container {
  border-radius: 6px !important;
}
footer {
  display: none !important;
}
"""

EDIT_PROMPT_EXAMPLES = {
    "Place Two Subjects Together": "Place the two uploaded subjects naturally in one coherent image, matching perspective and lighting, photorealistic blend.",
    "Remove Person from Scene": "Remove the person from the scene and reconstruct the background cleanly with realistic texture and lighting continuity.",
    "Replace Background": "Keep the main subject unchanged and replace the background with a cinematic city-at-night environment, realistic depth and shadows.",
    "Product Studio Shot": "Turn this into a premium studio product photo on a clean gradient backdrop, softbox lighting, crisp detail, minimal reflections.",
    "Anime Style Conversion": "Convert this image to high-quality anime style while preserving pose, composition, and key facial details.",
    "Face Cleanup + Detail": "Improve facial symmetry and skin detail subtly, keep identity intact, natural look, no over-smoothing.",
    "Outfit Change": "Keep the same person and pose, change outfit to modern streetwear, realistic fabric folds and texture.",
    "Color Grade Cinematic": "Apply cinematic color grading with teal-orange contrast, controlled highlights, rich shadows, and filmic tone.",
}


def _auth_headers(api_key: str) -> dict:
    key = (api_key or "").strip()
    if not key:
        raise ValueError("Missing Venice API key.")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _http_json(method: str, url: str, api_key: str, payload: dict | None = None) -> dict:
    data = None
    headers = _auth_headers(api_key)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}") from e


def _http_json_with_headers(method: str, url: str, api_key: str, payload: dict | None = None):
    data = None
    headers = _auth_headers(api_key)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return body, resp_headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}") from e


def _load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _append_jsonl(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 200):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if limit > 0:
        rows = rows[-limit:]
    return rows


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _balance_from_headers(headers: dict) -> str:
    usd = headers.get("x-venice-balance-usd", "n/a")
    diem = headers.get("x-venice-balance-diem", "n/a")
    req_left = headers.get("x-ratelimit-remaining-requests", "n/a")
    tok_left = headers.get("x-ratelimit-remaining-tokens", "n/a")
    return f"Balance USD={usd} | DIEM={diem} | req_left={req_left} | tok_left={tok_left}"


def refresh_account_status(api_key: str):
    out, headers = _http_json_with_headers("GET", f"{API_BASE}/api_keys/rate_limits", api_key=api_key)
    data = out.get("data", {}) or {}
    balances = data.get("balances", {}) or {}
    tier = (data.get("apiTier", {}) or {}).get("id", "unknown")
    next_epoch = data.get("nextEpochBegins", "n/a")
    usd = balances.get("USD", headers.get("x-venice-balance-usd", "n/a"))
    diem = balances.get("DIEM", headers.get("x-venice-balance-diem", "n/a"))
    req_left = headers.get("x-ratelimit-remaining-requests", "n/a")
    tok_left = headers.get("x-ratelimit-remaining-tokens", "n/a")

    summary = (
        f"Tier: {tier}\n"
        f"Balance: USD {usd} | DIEM {diem}\n"
        f"Remaining: requests {req_left} | tokens {tok_left}\n"
        f"Next epoch: {next_epoch}"
    )

    rate_limits = data.get("rateLimits", []) or []
    lines = []
    for item in rate_limits[:12]:
        model_id = item.get("apiModelId", "unknown")
        limits = item.get("rateLimits", []) or []
        parts = [f"{x.get('type', '?')}={x.get('amount', '?')}" for x in limits]
        lines.append(f"- {model_id}: " + ", ".join(parts))
    limits_preview = "\n".join(lines) if lines else "No rate limits found."
    raw_json = json.dumps(out, indent=2, ensure_ascii=False)
    return summary, limits_preview, raw_json


def format_account_view(summary_text: str, limits_text: str, selected_chat_model: str, selected_image_model: str):
    lines = [ln for ln in (limits_text or "").splitlines() if ln.strip()]
    selected_lines = []
    for ln in lines:
        if selected_chat_model and selected_chat_model in ln:
            selected_lines.append(f"Chat model limit: {ln.lstrip('- ').strip()}")
        if selected_image_model and selected_image_model in ln:
            selected_lines.append(f"Image model limit: {ln.lstrip('- ').strip()}")
    if not selected_lines:
        selected_lines.append("Selected model limits: not found in current top list.")
    compact = summary_text + "\n" + "\n".join(selected_lines[:2])
    return compact


def refresh_account_compact(api_key: str, selected_chat_model: str, selected_image_model: str):
    try:
        summary, limits, raw = refresh_account_status(api_key)
        compact = format_account_view(summary, limits, selected_chat_model, selected_image_model)
        lines = compact.splitlines()
        tier = lines[0].replace("Tier: ", "") if len(lines) > 0 else "n/a"
        bal = lines[1].replace("Balance: ", "") if len(lines) > 1 else "USD n/a | DIEM n/a"
        rem = lines[2].replace("Remaining: ", "") if len(lines) > 2 else "requests n/a | tokens n/a"
        next_epoch = lines[3].replace("Next epoch: ", "") if len(lines) > 3 else "n/a"
        model_lines = [ln for ln in lines[4:] if ln.strip()]
        model_summary = "<br>".join(model_lines[:2]) if model_lines else "No selected-model limits found."
        card = (
            f"### Account Snapshot\n"
            f"- **Tier:** `{tier}`\n"
            f"- **Balance:** `{bal}`\n"
            f"- **Remaining:** `{rem}`\n"
            f"- **Next Epoch:** `{next_epoch}`\n"
            f"- **Selected Model Limits:** {model_summary}"
        )
        return card, (raw or "")[:12000]
    except Exception as e:
        return f"### Account Snapshot\n- Error: `{e}`", ""


def save_prompt_template(name: str, prompt: str, negative_prompt: str):
    name = (name or "").strip()
    if not name:
        return "Template name required.", gr.update()
    data = _load_json(PROMPT_LIBRARY_PATH, {"templates": {}})
    templates = data.get("templates", {}) or {}
    templates[name] = {
        "prompt": (prompt or "").strip(),
        "negative_prompt": (negative_prompt or "").strip(),
    }
    data["templates"] = templates
    PROMPT_LIBRARY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    choices = sorted(templates.keys())
    return f"Saved template: {name}", gr.update(choices=choices, value=name)


def load_prompt_template(name: str):
    data = _load_json(PROMPT_LIBRARY_PATH, {"templates": {}})
    tpl = (data.get("templates", {}) or {}).get(name or "", {})
    return tpl.get("prompt", ""), tpl.get("negative_prompt", ""), f"Loaded template: {name}"


def apply_prompt_example(example_name: str):
    prompt = EDIT_PROMPT_EXAMPLES.get(example_name or "", "")
    return prompt, f"Applied example: {example_name}"


def refresh_prompt_templates():
    data = _load_json(PROMPT_LIBRARY_PATH, {"templates": {}})
    names = sorted((data.get("templates", {}) or {}).keys())
    return gr.update(choices=names, value=(names[0] if names else None))


def api_health_check(api_key: str):
    started = time.time()
    out, _ = _http_json_with_headers("GET", f"{API_BASE}/models?type=text", api_key=api_key)
    dt = time.time() - started
    count = len(out.get("data", []) or [])
    return f"Health OK in {dt:.2f}s | text models fetched: {count}"


def load_saved_settings():
    if not CONFIG_PATH.exists():
        return "", DEFAULT_CHAT_MODEL, DEFAULT_IMAGE_MODEL
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return (
            data.get("api_key", ""),
            data.get("default_chat_model", DEFAULT_CHAT_MODEL),
            data.get("default_image_model", DEFAULT_IMAGE_MODEL),
        )
    except Exception:
        return "", DEFAULT_CHAT_MODEL, DEFAULT_IMAGE_MODEL


def save_settings(api_key: str, default_chat_model: str, default_image_model: str):
    payload = {
        "api_key": (api_key or "").strip(),
        "default_chat_model": (default_chat_model or "").strip() or DEFAULT_CHAT_MODEL,
        "default_image_model": (default_image_model or "").strip() or DEFAULT_IMAGE_MODEL,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return "Saved settings to local app config. API key will be reused automatically next launch."


def fetch_models(api_key: str, model_type: str):
    q = urllib.parse.urlencode({"type": model_type})
    out = _http_json("GET", f"{API_BASE}/models?{q}", api_key=api_key)
    items = out.get("data", [])
    choices = []
    for m in items:
        mid = m.get("id", "")
        ms = m.get("model_spec", {}) or {}
        name = ms.get("name", mid)
        choices.append((f"{name} ({mid})", mid))
    choices = sorted(choices, key=lambda x: x[1])
    return choices


def _rank_model(model_id: str, preferred: list[str]) -> tuple:
    mid = (model_id or "").lower()
    for idx, token in enumerate(preferred):
        if token.lower() in mid:
            return (idx, mid)
    return (len(preferred), mid)


def _sorted_model_ids(choices: list[tuple[str, str]], preferred: list[str]) -> list[str]:
    vals = [c[1] for c in choices if c[1]]
    return sorted(vals, key=lambda v: _rank_model(v, preferred))


def _looks_like_image_request(text: str) -> bool:
    lower = (text or "").lower()
    return any(word in lower for word in IMAGE_INTENT_WORDS)


def _format_image_memory(assets: list[dict]) -> str:
    if not assets:
        return "No images generated in this chat yet."
    lines = []
    for idx, asset in enumerate(assets[-5:], start=max(1, len(assets) - 4)):
        prompt = str(asset.get("prompt", "")).strip()
        if len(prompt) > 160:
            prompt = prompt[:157] + "..."
        lines.append(
            f"{idx}. {asset.get('model', 'unknown')} | {asset.get('path', '')}\n"
            f"   prompt: {prompt}"
        )
    return "\n".join(lines)


def _build_contextual_image_prompt(user_text: str, assets: list[dict]) -> str:
    text = (user_text or "").strip()
    if not assets:
        return text

    lower = text.lower()
    followup_tokens = [
        "her",
        "him",
        "them",
        "it",
        "same",
        "previous",
        "last",
        "again",
        "different",
        "change",
        "place",
        "pose",
        "position",
        "move",
        "make this",
        "make her",
        "make him",
    ]
    if not any(token in lower for token in followup_tokens):
        return text

    last = assets[-1]
    previous_prompt = str(last.get("prompt", "")).strip()
    previous_model = str(last.get("model", "")).strip()
    previous_path = str(last.get("path", "")).strip()
    return (
        "Create a new image as a follow-up to the previous generated image. "
        "Use the previous prompt as visual continuity/context, while applying the new user request. "
        f"Previous image model: {previous_model}. "
        f"Previous saved image path for reference context: {previous_path}. "
        f"Previous prompt: {previous_prompt}. "
        f"New user request: {text}."
    )


def _image_memory_system_message(assets: list[dict]) -> dict | None:
    if not assets:
        return None
    latest = assets[-1]
    content = (
        "Session image memory: The user has generated images in this chat. "
        "When they refer to the latest image with words like it, this, her, him, same, previous, "
        "or ask for changes, use this memory. "
        f"Latest image model: {latest.get('model', 'unknown')}. "
        f"Latest saved path: {latest.get('path', '')}. "
        f"Latest prompt: {latest.get('prompt', '')}."
    )
    return {"role": "system", "content": content}


def refresh_chat_models(api_key: str):
    choices = fetch_models(api_key, "text")
    vals = _sorted_model_ids(choices, PREFERRED_CHAT_MODELS)
    default = DEFAULT_CHAT_MODEL if DEFAULT_CHAT_MODEL in vals else (vals[0] if vals else None)
    return gr.update(choices=vals, value=default), f"Loaded {len(vals)} chat models. Recommended agent models are sorted first."


def refresh_image_models(api_key: str):
    choices = fetch_models(api_key, "image")
    vals = _sorted_model_ids(choices, PREFERRED_IMAGE_MODELS)
    chroma = [v for v in vals if "chroma" in v.lower()]
    if DEFAULT_IMAGE_MODEL in vals:
        default = DEFAULT_IMAGE_MODEL
    elif chroma:
        default = chroma[0]
    else:
        default = vals[0] if vals else DEFAULT_IMAGE_MODEL
    return gr.update(choices=vals, value=default), f"Loaded {len(vals)} image models. Image generators are sorted with Chroma/preferred models first."


def filter_chroma_models(api_key: str):
    choices = fetch_models(api_key, "image")
    vals = [c[1] for c in choices if "chroma" in c[1].lower()]
    default = DEFAULT_IMAGE_MODEL if DEFAULT_IMAGE_MODEL in vals else (vals[0] if vals else DEFAULT_IMAGE_MODEL)
    msg = f"Found {len(vals)} model(s) containing 'chroma'."
    return gr.update(choices=vals, value=default), msg


def refresh_edit_models(api_key: str):
    choices = fetch_models(api_key, "image")
    all_vals = [c[1] for c in choices]
    vals = [v for v in all_vals if "edit" in v.lower()]
    if not vals:
        vals = all_vals
    lower_vals = [v.lower() for v in vals]
    if "qwen-edit" in lower_vals:
        default = vals[lower_vals.index("qwen-edit")]
    elif "firered-image-edit" in lower_vals:
        default = vals[lower_vals.index("firered-image-edit")]
    elif "venice-sd35" in lower_vals:
        default = vals[lower_vals.index("venice-sd35")]
    else:
        default = vals[0] if vals else None
    return gr.update(choices=vals, value=default), f"Loaded {len(vals)} model(s) for edit."


def startup_status(saved_api_key: str):
    has_key = bool((saved_api_key or "").strip())
    key_light = "[OK] API key loaded from local config" if has_key else "[SETUP] API key missing. Paste it once and save."
    models_light = "[READY] Refresh models when you want the live Venice list."
    return f"{key_light}\n{models_light}"


def api_ready_status(api_key: str):
    if (api_key or "").strip():
        return "[OK] API key present"
    return "[SETUP] API key missing"


def _pil_to_data_url(image_obj: Image.Image) -> str:
    buf = io.BytesIO()
    image_obj.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _pil_to_base64(image_obj: Image.Image) -> str:
    buf = io.BytesIO()
    image_obj.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def chat_once(
    api_key: str,
    model: str,
    user_text: str,
    history: list,
    venice_messages: list,
    system_prompt: str,
    character_slug: str,
    web_search_mode: str,
    temperature: float,
    max_tokens: int,
    disable_thinking: bool,
    agent_image_mode: str,
    agent_image_model: str,
    agent_image_negative: str,
    agent_image_width: int,
    agent_image_height: int,
    agent_image_steps: int,
    agent_image_cfg: float,
    agent_image_seed: int,
    agent_image_safe_mode: bool,
    generated_assets: list,
):
    text = (user_text or "").strip()
    assets = list(generated_assets or [])
    if not text:
        return history, venice_messages, "", "Please enter a message.", None, assets, _format_image_memory(assets)

    msgs = list(venice_messages or [])
    if system_prompt.strip() and (not msgs or msgs[0].get("role") != "system"):
        msgs.insert(0, {"role": "system", "content": system_prompt.strip()})
    msgs.append({"role": "user", "content": text})

    image_mode = (agent_image_mode or "Auto image requests").strip().lower()
    should_generate_image = (
        image_mode.startswith("always")
        or (image_mode.startswith("auto") and _looks_like_image_request(text))
    )

    if should_generate_image:
        image_prompt = _build_contextual_image_prompt(text, assets)
        image, status, out_path = _generate_image_result(
            api_key=api_key,
            model=agent_image_model,
            prompt=image_prompt,
            negative_prompt=agent_image_negative,
            width=agent_image_width,
            height=agent_image_height,
            steps=agent_image_steps,
            cfg_scale=agent_image_cfg,
            variants=1,
            seed=agent_image_seed,
            safe_mode=agent_image_safe_mode,
            source="agent-chat",
        )
        assets.append({
            "ts": time.strftime("%Y%m%d-%H%M%S"),
            "model": agent_image_model,
            "path": str(out_path),
            "prompt": image_prompt,
            "user_request": text,
            "width": int(agent_image_width),
            "height": int(agent_image_height),
        })
        assets = assets[-20:]
        assistant = (
            f"Generated image with {agent_image_model}.\n"
            f"User request: {text}\n"
            f"Image prompt: {image_prompt}\n"
            f"Saved: {out_path}"
        )
        msgs.append({"role": "assistant", "content": assistant})
        ui_history = list(history or [])
        ui_history.append({"role": "user", "content": text})
        ui_history.append({"role": "assistant", "content": assistant})
        return ui_history, msgs, "", f"Agent image mode: {status}", image, assets, _format_image_memory(assets)

    api_msgs = list(msgs)
    memory_msg = _image_memory_system_message(assets)
    if memory_msg and api_msgs and api_msgs[-1].get("role") == "user":
        api_msgs = api_msgs[:-1] + [memory_msg, api_msgs[-1]]

    payload = {
        "model": model,
        "messages": api_msgs,
        "temperature": float(temperature),
        "max_completion_tokens": int(max_tokens),
        "stream": False,
        "venice_parameters": {
            "character_slug": (character_slug or "").strip() or None,
            "enable_web_search": web_search_mode,
            "disable_thinking": bool(disable_thinking),
            "strip_thinking_response": True,
            "include_venice_system_prompt": True,
        },
    }
    t0 = time.time()
    out = _http_json("POST", f"{API_BASE}/chat/completions", api_key=api_key, payload=payload)
    dt = time.time() - t0
    choices = out.get("choices", [])
    if not choices:
        raise RuntimeError("No chat choices returned.")
    msg = choices[0].get("message", {}) or {}
    assistant = msg.get("content", "")
    msgs.append({"role": "assistant", "content": assistant})

    ui_history = list(history or [])
    ui_history.append({"role": "user", "content": text})
    ui_history.append({"role": "assistant", "content": assistant})
    usage = out.get("usage", {}) or {}
    status = (
        f"Chat ok in {dt:.2f}s | model={out.get('model', model)} | "
        f"tokens prompt={usage.get('prompt_tokens', '?')} completion={usage.get('completion_tokens', '?')}"
    )
    return ui_history, msgs, "", status, None, assets, _format_image_memory(assets)


def clear_chat():
    return [], [], "", "Chat cleared.", None, [], _format_image_memory([])


def generate_image(
    api_key: str,
    model: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    variants: int,
    seed: int,
    safe_mode: bool,
):
    if not (prompt or "").strip():
        raise ValueError("Prompt is required.")
    image, status, _ = _generate_image_result(
        api_key=api_key,
        model=model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        variants=variants,
        seed=seed,
        safe_mode=safe_mode,
        source="image-tab",
    )
    return image, status


def _generate_image_result(
    api_key: str,
    model: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    variants: int,
    seed: int,
    safe_mode: bool,
    source: str,
):
    payload = {
        "model": model,
        "prompt": prompt.strip(),
        "negative_prompt": (negative_prompt or "").strip(),
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
        "variants": int(variants),
        "seed": int(seed),
        "safe_mode": bool(safe_mode),
        "format": "png",
        "return_binary": False,
    }
    t0 = time.time()
    out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/generate", api_key=api_key, payload=payload)
    dt = time.time() - t0
    images = out.get("images", [])
    if not images:
        raise RuntimeError("No image data returned.")
    raw = base64.b64decode(images[0])
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    model_slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in model)
    out_path = OUTPUTS_DIR / f"venice-{model_slug}-{stamp}.png"
    image.save(out_path)
    meta = {
        "ts": stamp,
        "model": model,
        "prompt": prompt.strip(),
        "negative_prompt": (negative_prompt or "").strip(),
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
        "variants": int(variants),
        "seed": int(seed),
        "safe_mode": bool(safe_mode),
        "source": source,
    }
    (out_path.with_suffix(".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    timing = out.get("timing", {}) or {}
    balance = _balance_from_headers(headers)
    balance_usd = headers.get("x-venice-balance-usd")
    history_row = {
        "id": f"{stamp}-{model_slug}",
        "ts": stamp,
        "image_path": str(out_path),
        "meta_path": str(out_path.with_suffix('.json')),
        "model": model,
        "prompt": prompt.strip(),
        "negative_prompt": (negative_prompt or "").strip(),
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "cfg_scale": float(cfg_scale),
        "variants": int(variants),
        "seed": int(seed),
        "safe_mode": bool(safe_mode),
        "inference_ms": timing.get("inferenceDuration"),
        "queue_ms": timing.get("inferenceQueueTime"),
        "balance_usd_after": balance_usd,
    }
    _append_jsonl(IMAGE_HISTORY_PATH, history_row)
    status = (
        f"Image ok in {dt:.2f}s | model={model} | variants={variants} | "
        f"queue={timing.get('inferenceQueueTime', '?')}ms infer={timing.get('inferenceDuration', '?')}ms\n"
        f"Saved: {out_path}\n{balance}"
    )
    return image, status, out_path


def edit_image_from_reference(
    api_key: str,
    model: str,
    edit_prompt: str,
    negative_prompt: str,
    source_image,
    safe_mode: bool,
    seed: int,
):
    if source_image is None:
        raise ValueError("Please upload a reference image.")
    if not (edit_prompt or "").strip():
        raise ValueError("Edit prompt is required.")

    if hasattr(source_image, "convert"):
        src = source_image.convert("RGB")
    else:
        src = Image.open(source_image).convert("RGB")

    if not (model or "").strip():
        raise ValueError("Please select an edit model.")

    payload = {
        "modelId": model,
        "prompt": edit_prompt.strip(),
        "image": _pil_to_base64(src),
        "safe_mode": bool(safe_mode),
    }
    t0 = time.time()
    try:
        out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/edit", api_key=api_key, payload=payload)
    except RuntimeError as e:
        err = str(e)
        if "Invalid or corrupt image" in err:
            payload_retry = dict(payload)
            payload_retry["image"] = _pil_to_data_url(src)
            out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/edit", api_key=api_key, payload=payload_retry)
        elif "modelId" in err or "Invalid model id" in err:
            payload_fallback = dict(payload)
            payload_fallback.pop("modelId", None)
            payload_fallback["model"] = model
            out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/edit", api_key=api_key, payload=payload_fallback)
        else:
            raise
    dt = time.time() - t0
    images = out.get("images", [])
    if not images:
        raise RuntimeError("No edited image data returned.")

    raw = base64.b64decode(images[0])
    edited = Image.open(io.BytesIO(raw)).convert("RGB")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    model_slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (model or "edit"))
    out_path = OUTPUTS_DIR / f"venice-edit-{model_slug}-{stamp}.png"
    edited.save(out_path)

    meta = {
        "ts": stamp,
        "type": "edit",
        "model": model,
        "prompt": edit_prompt.strip(),
        "negative_prompt": (negative_prompt or "").strip(),
        "seed": int(seed),
        "safe_mode": bool(safe_mode),
        "source_size": list(src.size),
    }
    (out_path.with_suffix(".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    timing = out.get("timing", {}) or {}
    history_row = {
        "id": f"{stamp}-edit-{model_slug}",
        "ts": stamp,
        "image_path": str(out_path),
        "meta_path": str(out_path.with_suffix(".json")),
        "model": model,
        "prompt": edit_prompt.strip(),
        "negative_prompt": (negative_prompt or "").strip(),
        "width": int(src.size[0]),
        "height": int(src.size[1]),
        "steps": None,
        "cfg_scale": None,
        "variants": 1,
        "seed": int(seed),
        "safe_mode": bool(safe_mode),
        "inference_ms": timing.get("inferenceDuration"),
        "queue_ms": timing.get("inferenceQueueTime"),
        "balance_usd_after": headers.get("x-venice-balance-usd"),
        "edit_mode": True,
    }
    _append_jsonl(IMAGE_HISTORY_PATH, history_row)

    status = (
        f"Edit ok in {dt:.2f}s | model={model}\n"
        f"queue={timing.get('inferenceQueueTime', '?')}ms infer={timing.get('inferenceDuration', '?')}ms\n"
        f"Saved: {out_path}\n{_balance_from_headers(headers)}"
    )
    return edited, status


def multi_edit_image(
    api_key: str,
    model: str,
    prompt: str,
    image1,
    image2,
    image3,
    aspect_ratio: str,
    resolution: str,
    output_format: str,
    quality: str,
    safe_mode: bool,
):
    if not (prompt or "").strip():
        raise ValueError("Prompt is required.")
    if not (model or "").strip():
        raise ValueError("Please select a multi-edit model.")

    imgs = []
    for src in [image1, image2, image3]:
        if src is None:
            continue
        if hasattr(src, "convert"):
            img = src.convert("RGB")
        else:
            img = Image.open(src).convert("RGB")
        imgs.append(_pil_to_base64(img))

    if not imgs:
        raise ValueError("Please upload at least one image.")

    payload = {
        "modelId": model,
        "prompt": prompt.strip(),
        "images": imgs,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_format": output_format,
        "safe_mode": bool(safe_mode),
    }
    t0 = time.time()
    try:
        out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/multi-edit", api_key=api_key, payload=payload)
    except RuntimeError as e:
        if "Invalid or corrupt image" in str(e):
            payload_retry = dict(payload)
            payload_retry["images"] = []
            for src in [image1, image2, image3]:
                if src is None:
                    continue
                if hasattr(src, "convert"):
                    img = src.convert("RGB")
                else:
                    img = Image.open(src).convert("RGB")
                payload_retry["images"].append(_pil_to_data_url(img))
            out, headers = _http_json_with_headers("POST", f"{API_BASE}/image/multi-edit", api_key=api_key, payload=payload_retry)
        else:
            raise
    dt = time.time() - t0
    images = out.get("images", [])
    if not images:
        raise RuntimeError("No multi-edit image returned.")

    raw = base64.b64decode(images[0])
    edited = Image.open(io.BytesIO(raw)).convert("RGB")
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    model_slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (model or "multi_edit"))
    out_path = OUTPUTS_DIR / f"venice-multiedit-{model_slug}-{stamp}.png"
    edited.save(out_path)

    meta = {
        "ts": stamp,
        "type": "multi-edit",
        "model": model,
        "prompt": prompt.strip(),
        "images_count": len(imgs),
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_format": output_format,
        "quality": quality,
        "safe_mode": bool(safe_mode),
    }
    (out_path.with_suffix(".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    timing = out.get("timing", {}) or {}
    history_row = {
        "id": f"{stamp}-multiedit-{model_slug}",
        "ts": stamp,
        "image_path": str(out_path),
        "meta_path": str(out_path.with_suffix(".json")),
        "model": model,
        "prompt": prompt.strip(),
        "negative_prompt": "",
        "width": None,
        "height": None,
        "steps": None,
        "cfg_scale": None,
        "variants": 1,
        "seed": None,
        "safe_mode": bool(safe_mode),
        "inference_ms": timing.get("inferenceDuration"),
        "queue_ms": timing.get("inferenceQueueTime"),
        "balance_usd_after": headers.get("x-venice-balance-usd"),
        "multi_edit_mode": True,
    }
    _append_jsonl(IMAGE_HISTORY_PATH, history_row)

    status = (
        f"Multi-edit ok in {dt:.2f}s | model={model} | layers={len(imgs)}\n"
        f"queue={timing.get('inferenceQueueTime', '?')}ms infer={timing.get('inferenceDuration', '?')}ms\n"
        f"Saved: {out_path}\n{_balance_from_headers(headers)}"
    )
    return edited, status


def recommended_image_settings(model_id: str):
    mid = (model_id or "").lower()
    # Safe defaults first
    width, height, steps, cfg, variants, safe_mode = 1024, 1024, 8, 7.5, 1, True
    # Heuristics by model family
    if "flux" in mid:
        steps, cfg = 18, 3.5
    elif "sdxl" in mid:
        steps, cfg = 30, 7.0
    elif "sd35" in mid or "chroma" in mid:
        steps, cfg = 12, 5.0
    elif "turbo" in mid:
        steps, cfg = 6, 2.5
    return (
        gr.update(value=width),
        gr.update(value=height),
        gr.update(value=steps),
        gr.update(value=cfg),
        gr.update(value=variants),
        gr.update(value=safe_mode),
        f"Applied recommended settings for {model_id or 'selected model'}.",
    )


def _cost_summary(entries: list[dict]) -> str:
    if not entries:
        return "No history yet."
    total = len(entries)
    last_model = entries[-1].get("model", "n/a")
    # Estimate spend by balance decreases between consecutive entries.
    spend = 0.0
    prev = None
    known_points = 0
    for e in entries:
        b = e.get("balance_usd_after")
        try:
            cur = float(b)
            known_points += 1
        except Exception:
            continue
        if prev is not None and cur <= prev:
            spend += (prev - cur)
        prev = cur
    return (
        f"Images generated: {total}\n"
        f"Last model: {last_model}\n"
        f"Known balance points: {known_points}\n"
        f"Estimated spend from balance deltas: ${spend:.6f}"
    )


def refresh_history(limit: int, model_filter: str, date_filter: str):
    entries = _read_jsonl(IMAGE_HISTORY_PATH, int(limit))
    mf = (model_filter or "").strip().lower()
    df = (date_filter or "").strip()
    if mf:
        entries = [e for e in entries if mf in str(e.get("model", "")).lower()]
    if df:
        entries = [e for e in entries if str(e.get("ts", "")).startswith(df)]
    entries = list(reversed(entries))
    choices = []
    gallery = []
    table = []
    for e in entries:
        image_path = e.get("image_path", "")
        label = f"{e.get('ts','?')} | {e.get('model','?')} | seed={e.get('seed','?')}"
        choices.append((label, e.get("id", "")))
        if image_path:
            gallery.append((image_path, label))
        table.append([
            e.get("ts", ""),
            e.get("model", ""),
            e.get("width", ""),
            e.get("height", ""),
            e.get("steps", ""),
            e.get("cfg_scale", ""),
            e.get("seed", ""),
        ])
    summary = _cost_summary(list(reversed(entries)))
    return (
        gr.update(choices=[c[1] for c in choices], value=(choices[0][1] if choices else None)),
        gr.update(choices=sorted({str(e.get("model", "")) for e in entries if e.get("model")}), value=(model_filter or None)),
        gallery,
        table,
        summary,
    )


def load_history_item(selected_id: str):
    entries = _read_jsonl(IMAGE_HISTORY_PATH, 5000)
    target = None
    for e in entries:
        if e.get("id") == selected_id:
            target = e
            break
    if not target:
        return "", "", DEFAULT_IMAGE_MODEL, 1024, 1024, 8, 7.5, 1, 0, True, "No history item selected."
    return (
        target.get("prompt", ""),
        target.get("negative_prompt", ""),
        target.get("model", DEFAULT_IMAGE_MODEL),
        int(target.get("width", 1024)),
        int(target.get("height", 1024)),
        int(target.get("steps", 8)),
        float(target.get("cfg_scale", 7.5)),
        int(target.get("variants", 1)),
        int(target.get("seed", 0)),
        bool(target.get("safe_mode", True)),
        f"Loaded history item {selected_id}",
    )


def delete_history_item(selected_id: str):
    if not selected_id:
        return "Pick a history item first."
    rows = _read_jsonl(IMAGE_HISTORY_PATH, 100000)
    keep = []
    target = None
    for r in rows:
        if r.get("id") == selected_id and target is None:
            target = r
            continue
        keep.append(r)
    if target is None:
        return "History item not found."
    image_path = Path(target.get("image_path", ""))
    meta_path = Path(target.get("meta_path", ""))
    if image_path.exists():
        image_path.unlink()
    if meta_path.exists():
        meta_path.unlink()
    _write_jsonl(IMAGE_HISTORY_PATH, keep)
    return f"Deleted history item: {selected_id}"


def build_app():
    saved_key, saved_chat_model, saved_image_model = load_saved_settings()
    saved_image_model = DEFAULT_IMAGE_MODEL

    with gr.Blocks(title="FEDDAKALKUN Venice Agent Studio") as app:
        gr.HTML(
            """
            <section class="fk-hero">
              <div class="fk-kicker">FEDDAKALKUN App Factory</div>
              <h1>Venice Agent Studio</h1>
              <p>Agent chat, Chroma-preferred image generation, saved outputs, prompt templates, and account visibility in one local Windows app.</p>
            </section>
            """
        )

        with gr.Accordion("Setup & Account", open=not bool((saved_key or "").strip())):
            api_key = gr.Textbox(label="Venice API Key", type="password", value=saved_key)
            with gr.Row():
                default_chat_model = gr.Textbox(label="Default Chat Model", value=saved_chat_model)
                default_image_model = gr.Textbox(label="Default Image Model", value=saved_image_model)
            with gr.Row():
                save_btn = gr.Button("Save Settings", variant="primary")
                account_btn = gr.Button("Refresh Account / Credits")
                health_btn = gr.Button("Health Check")
            ready_status = gr.Markdown(startup_status(saved_key), elem_classes=["fk-statusbar"])
            settings_status = gr.Textbox(label="Settings Status", interactive=False)
            account_status = gr.Markdown("### Account Snapshot\nPress **Refresh Account / Credits**.")
            with gr.Accordion("Debug JSON", open=False):
                account_raw = gr.Textbox(label="Account Raw JSON", lines=14, interactive=False)
            health_status = gr.Textbox(label="API Health", interactive=False)

        with gr.Tabs():
            with gr.Tab("Agent Chat"):
                with gr.Row(elem_classes=["fk-workspace"]):
                    with gr.Column(scale=7, elem_classes=["fk-left"]):
                        chatbot = gr.Chatbot(label="Conversation", height=560)
                        chat_image_out = gr.Image(label="Agent Image Preview", type="pil", height=320)
                        agent_memory = gr.Textbox(
                            label="Session Image Memory",
                            value=_format_image_memory([]),
                            lines=5,
                            interactive=False,
                        )
                        user_input = gr.Textbox(label="Message", placeholder="Ask anything...", lines=3)
                        with gr.Row():
                            send_btn = gr.Button("Send", variant="primary")
                            clear_btn = gr.Button("Clear")
                        chat_status = gr.Textbox(label="Status", interactive=False, lines=2)
                    with gr.Column(scale=4, elem_classes=["fk-right"]):
                        with gr.Row():
                            chat_model = gr.Dropdown(label="Chat Model", choices=[saved_chat_model], value=saved_chat_model)
                            refresh_chat_btn = gr.Button("Refresh")
                        with gr.Accordion("Agent Settings", open=True):
                            system_prompt = gr.Textbox(
                                label="System Prompt",
                                value="You are a helpful expert assistant. Be clear, practical, and concise.",
                                lines=5,
                            )
                            character_slug = gr.Textbox(label="Character Slug", value="venice")
                            web_search_mode = gr.Dropdown(
                                label="Web Search",
                                choices=["off", "auto", "on"],
                                value="auto",
                            )
                            disable_thinking = gr.Checkbox(label="Disable Thinking", value=True)
                            temperature = gr.Slider(0.0, 2.0, value=0.7, step=0.05, label="Temperature")
                            max_tokens = gr.Slider(64, 4096, value=1024, step=64, label="Max Tokens")
                        with gr.Accordion("Agent Image Mode", open=True):
                            agent_image_mode = gr.Dropdown(
                                label="Image Behavior",
                                choices=[
                                    "Auto image requests",
                                    "Chat only",
                                    "Always generate image",
                                ],
                                value="Auto image requests",
                            )
                            with gr.Row():
                                agent_image_model = gr.Dropdown(
                                    label="Image Model",
                                    choices=[saved_image_model],
                                    value=saved_image_model,
                                )
                                refresh_agent_img_btn = gr.Button("Refresh")
                            agent_image_negative = gr.Textbox(
                                label="Negative Prompt",
                                value="low quality, blurry, distorted, bad anatomy, artifacts",
                                lines=2,
                            )
                            with gr.Row():
                                agent_image_width = gr.Slider(256, 1280, value=1024, step=64, label="Width")
                                agent_image_height = gr.Slider(256, 1280, value=1024, step=64, label="Height")
                            with gr.Row():
                                agent_image_steps = gr.Slider(1, 30, value=8, step=1, label="Steps")
                                agent_image_cfg = gr.Slider(0.1, 20.0, value=5.0, step=0.1, label="CFG")
                            with gr.Row():
                                agent_image_seed = gr.Number(label="Seed", value=0, precision=0)
                                agent_image_safe_mode = gr.Checkbox(label="Safe Mode", value=True)
                ui_history = gr.State([])
                venice_messages = gr.State([])
                generated_assets = gr.State([])

            with gr.Tab("Image Generation"):
                with gr.Row(elem_classes=["fk-workspace"]):
                    with gr.Column(scale=5, elem_classes=["fk-left"]):
                        with gr.Row():
                            image_model = gr.Dropdown(label="Image Model", choices=[saved_image_model], value=saved_image_model)
                            refresh_img_btn = gr.Button("Refresh")
                            chroma_btn = gr.Button("Chroma")
                        prompt = gr.Textbox(label="Prompt", lines=5)
                        negative_prompt = gr.Textbox(label="Negative Prompt", lines=2)
                        with gr.Accordion("Prompt Templates", open=False):
                            with gr.Row():
                                template_name = gr.Textbox(label="Template Name")
                                save_template_btn = gr.Button("Save")
                            with gr.Row():
                                template_pick = gr.Dropdown(label="Template", choices=[])
                                load_template_btn = gr.Button("Load")
                                refresh_tpl_btn = gr.Button("Refresh")
                        with gr.Accordion("Generation Settings", open=True):
                            with gr.Row():
                                width = gr.Slider(256, 1280, value=1024, step=64, label="Width")
                                height = gr.Slider(256, 1280, value=1024, step=64, label="Height")
                            with gr.Row():
                                steps = gr.Slider(1, 30, value=8, step=1, label="Steps")
                                cfg_scale = gr.Slider(0.1, 20.0, value=7.5, step=0.1, label="CFG")
                            with gr.Row():
                                variants = gr.Slider(1, 4, value=1, step=1, label="Variants")
                                seed = gr.Number(label="Seed", value=0, precision=0)
                                safe_mode = gr.Checkbox(label="Safe Mode", value=True)
                        gen_btn = gr.Button("Generate Image", variant="primary")
                        image_status = gr.Textbox(label="Status", interactive=False, lines=5)
                    with gr.Column(scale=6, elem_classes=["fk-right", "fk-output"]):
                        image_out = gr.Image(label="Output", type="pil", height=640)

            with gr.Tab("History & Gallery"):
                with gr.Row():
                    history_limit = gr.Slider(10, 500, value=100, step=10, label="History Items")
                    refresh_history_btn = gr.Button("Refresh History")
                with gr.Row():
                    history_model_filter = gr.Dropdown(label="Model Filter", choices=[], allow_custom_value=True)
                    history_date_filter = gr.Textbox(label="Date Filter (YYYYMMDD)", placeholder="20260525")
                with gr.Row():
                    history_pick = gr.Dropdown(label="History Item", choices=[])
                    load_history_btn = gr.Button("Load Selected into Generator")
                    delete_history_btn = gr.Button("Delete Selected")
                history_gallery = gr.Gallery(label="Recent Outputs", columns=4, height=360)
                history_table = gr.Dataframe(
                    headers=["Timestamp", "Model", "W", "H", "Steps", "CFG", "Seed"],
                    datatype=["str", "str", "number", "number", "number", "number", "number"],
                    interactive=False,
                )
                cost_summary = gr.Textbox(label="Cost / Usage Summary", interactive=False, lines=4)

        save_btn.click(
            fn=save_settings,
            inputs=[api_key, default_chat_model, default_image_model],
            outputs=settings_status,
            api_name="save_settings",
        )
        api_key.change(
            fn=api_ready_status,
            inputs=api_key,
            outputs=ready_status,
            api_name="api_ready_status",
        )
        account_btn.click(
            fn=refresh_account_compact,
            inputs=[api_key, chat_model, image_model],
            outputs=[account_status, account_raw],
            api_name="refresh_account_status",
        )
        health_btn.click(
            fn=api_health_check,
            inputs=api_key,
            outputs=health_status,
            api_name="api_health_check",
        )
        refresh_chat_btn.click(
            fn=refresh_chat_models,
            inputs=api_key,
            outputs=[chat_model, chat_status],
            api_name="refresh_chat_models",
        ).then(fn=lambda: "[OK] Chat models loaded", inputs=None, outputs=ready_status)
        refresh_img_btn.click(
            fn=refresh_image_models,
            inputs=api_key,
            outputs=[image_model, image_status],
            api_name="refresh_image_models",
        ).then(fn=lambda: "[OK] Image models loaded. Chroma is preferred when available.", inputs=None, outputs=ready_status)
        refresh_agent_img_btn.click(
            fn=refresh_image_models,
            inputs=api_key,
            outputs=[agent_image_model, chat_status],
            api_name="refresh_agent_image_models",
        )
        chroma_btn.click(
            fn=filter_chroma_models,
            inputs=api_key,
            outputs=[image_model, image_status],
            api_name="filter_chroma_models",
        )
        image_model.change(
            fn=recommended_image_settings,
            inputs=image_model,
            outputs=[width, height, steps, cfg_scale, variants, safe_mode, image_status],
            api_name="apply_recommended_image_settings",
        )
        save_template_btn.click(
            fn=save_prompt_template,
            inputs=[template_name, prompt, negative_prompt],
            outputs=[image_status, template_pick],
            api_name="save_prompt_template",
        )
        load_template_btn.click(
            fn=load_prompt_template,
            inputs=template_pick,
            outputs=[prompt, negative_prompt, image_status],
            api_name="load_prompt_template",
        )
        refresh_tpl_btn.click(
            fn=refresh_prompt_templates,
            inputs=[],
            outputs=template_pick,
            api_name="refresh_prompt_templates",
        )
        def _safe_chat(*args):
            try:
                return chat_once(*args)
            except Exception as e:
                hist = list(args[3] or [])
                msgs = list(args[4] or [])
                assets = list(args[-1] or [])
                return hist, msgs, "", f"Chat error: {e}", None, assets, _format_image_memory(assets)

        def _safe_generate(*args):
            try:
                return generate_image(*args)
            except Exception as e:
                return None, f"Generate error: {e}"

        send_btn.click(
            fn=_safe_chat,
            inputs=[
                api_key,
                chat_model,
                user_input,
                ui_history,
                venice_messages,
                system_prompt,
                character_slug,
                web_search_mode,
                temperature,
                max_tokens,
                disable_thinking,
                agent_image_mode,
                agent_image_model,
                agent_image_negative,
                agent_image_width,
                agent_image_height,
                agent_image_steps,
                agent_image_cfg,
                agent_image_seed,
                agent_image_safe_mode,
                generated_assets,
            ],
            outputs=[chatbot, venice_messages, user_input, chat_status, chat_image_out, generated_assets, agent_memory],
            api_name="agent_chat",
        )
        clear_btn.click(
            fn=clear_chat,
            inputs=[],
            outputs=[chatbot, venice_messages, user_input, chat_status, chat_image_out, generated_assets, agent_memory],
            api_name="clear_chat",
        )
        gen_btn.click(
            fn=_safe_generate,
            inputs=[
                api_key,
                image_model,
                prompt,
                negative_prompt,
                width,
                height,
                steps,
                cfg_scale,
                variants,
                seed,
                safe_mode,
            ],
            outputs=[image_out, image_status],
            api_name="generate_image",
        )
        refresh_history_btn.click(
            fn=refresh_history,
            inputs=[history_limit, history_model_filter, history_date_filter],
            outputs=[history_pick, history_model_filter, history_gallery, history_table, cost_summary],
            api_name="refresh_history",
        )
        load_history_btn.click(
            fn=load_history_item,
            inputs=history_pick,
            outputs=[
                prompt,
                negative_prompt,
                image_model,
                width,
                height,
                steps,
                cfg_scale,
                variants,
                seed,
                safe_mode,
                image_status,
            ],
            api_name="load_history_item",
        )
        delete_history_btn.click(
            fn=delete_history_item,
            inputs=history_pick,
            outputs=image_status,
            api_name="delete_history_item",
        ).then(
            fn=refresh_history,
            inputs=[history_limit, history_model_filter, history_date_filter],
            outputs=[history_pick, history_model_filter, history_gallery, history_table, cost_summary],
        )

    return app


if __name__ == "__main__":
    app = build_app()
    app.queue(default_concurrency_limit=2).launch(server_name="127.0.0.1", server_port=7870, inbrowser=True, css=APP_CSS)
