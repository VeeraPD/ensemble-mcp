"""Minimal OpenAI-compatible chat-completions client (DeepSeek, OpenAI, OpenRouter, Ollama, ...)."""
import json
import os
import time
import urllib.error
import urllib.request


class ApiError(RuntimeError):
    pass


def load_api_key(cfg):
    """Environment first, then KEY=value in <root>/.env. Returns None when the provider needs no key."""
    name = cfg.provider.api_key_env
    if not name:
        return None
    key = os.environ.get(name)
    env_file = os.path.join(cfg.root, ".env")
    if not key and os.path.isfile(env_file):
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.strip().partition("=")
                if k == name:
                    key = v.strip().strip("\"'")
    if not key or key.startswith("paste-your-key"):
        raise ApiError(f"{name} is not set: export it or put it in {env_file}")
    return key


def chat(cfg, system, user, model):
    """Return (text, finish_reason, usage). Retries 429/5xx and network errors with backoff."""
    p = cfg.provider
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if p.max_tokens:
        payload["max_tokens"] = p.max_tokens
    headers = {"Content-Type": "application/json"}
    key = load_api_key(cfg)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps(payload).encode()
    last = None
    for attempt in range(p.max_retries):
        try:
            req = urllib.request.Request(p.chat_url, body, headers)
            with urllib.request.urlopen(req, timeout=p.timeout) as r:
                data = json.load(r)
            choice = data["choices"][0]
            return choice["message"]["content"] or "", choice.get("finish_reason"), data.get("usage", {})
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            last = ApiError(f"HTTP {e.code}: {detail}")
            if e.code not in (429, 500, 502, 503, 504):
                raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = ApiError(f"network error: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ApiError(f"unexpected response shape: {e}")
        if attempt < p.max_retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise last
