"""Configuration loading and validation. Stdlib only; config is JSON."""
import json
import os
from dataclasses import dataclass, field

CONFIG_NAMES = ("ensemble.json",)


class ConfigError(Exception):
    pass


@dataclass
class Provider:
    base_url: str = "https://api.deepseek.com"
    api_key_env: str = "DEEPSEEK_API_KEY"
    models: list = field(default_factory=lambda: ["deepseek-chat", "deepseek-reasoner"])
    default_model: str = "deepseek-chat"
    timeout: int = 900
    max_retries: int = 3
    max_tokens: int = 0  # 0 = provider default

    @property
    def chat_url(self):
        base = self.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else base + "/chat/completions"


@dataclass
class Role:
    name: str
    owns: list
    instructions_file: str = ""
    instructions: str = ""
    context: list = field(default_factory=list)
    description: str = ""


@dataclass
class Config:
    root: str
    path: str
    provider: Provider
    roles: dict
    shared_context: list = field(default_factory=list)
    max_context_bytes: int = 120_000
    max_parallel: int = 5
    audit_log: bool = True


def find_config(start=None):
    """Explicit env var wins, then walk up from `start` looking for ensemble.json."""
    env = os.environ.get("ENSEMBLE_CONFIG")
    if env:
        return os.path.abspath(env)
    d = os.path.abspath(start or os.getcwd())
    while True:
        for name in CONFIG_NAMES:
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(d)
        if parent == d:
            raise ConfigError("ensemble.json not found (use --config or ENSEMBLE_CONFIG)")
        d = parent


def _str_list(value, where):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where} must be a list of strings")
    return value


def load_config(path):
    path = os.path.abspath(path)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"config not found: {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON: {e}")
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")

    base = os.path.dirname(path)
    root = os.path.realpath(os.path.join(base, raw.get("root", ".")))

    praw = raw.get("provider") or {}
    p = Provider()
    for key in ("base_url", "api_key_env", "default_model"):
        if key in praw:
            setattr(p, key, str(praw[key]))
    if "models" in praw:
        p.models = _str_list(praw["models"], "provider.models")
    for key in ("timeout", "max_retries", "max_tokens"):
        if key in praw:
            if not isinstance(praw[key], int) or praw[key] < 0:
                raise ConfigError(f"provider.{key} must be a non-negative integer")
            setattr(p, key, praw[key])
    if p.default_model not in p.models:
        raise ConfigError(f"provider.default_model '{p.default_model}' not in provider.models")

    rroles = raw.get("roles")
    if not isinstance(rroles, dict) or not rroles:
        raise ConfigError("config needs a non-empty 'roles' object")
    roles = {}
    for name, r in rroles.items():
        if not isinstance(r, dict):
            raise ConfigError(f"role '{name}' must be an object")
        owns = _str_list(r.get("owns", []), f"roles.{name}.owns")
        if not owns:
            raise ConfigError(f"role '{name}' must own at least one path")
        for o in owns:
            norm = os.path.normpath(o)
            if os.path.isabs(norm) or norm.startswith("..") or norm == ".":
                raise ConfigError(f"role '{name}' owns an unsafe path: {o!r} (must be a project-relative subpath)")
        roles[name] = Role(
            name=name,
            owns=[os.path.normpath(o) for o in owns],
            instructions_file=r.get("instructions_file", ""),
            instructions=r.get("instructions", ""),
            context=_str_list(r.get("context", []), f"roles.{name}.context"),
            description=r.get("description", ""),
        )

    return Config(
        root=root,
        path=path,
        provider=p,
        roles=roles,
        shared_context=_str_list(raw.get("shared_context", []), "shared_context"),
        max_context_bytes=int(raw.get("max_context_bytes", 120_000)),
        max_parallel=max(1, min(int(raw.get("max_parallel", 5)), 16)),
        audit_log=bool(raw.get("audit_log", True)),
    )
