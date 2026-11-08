"""Application configuration.

Key lookup order: GUI/config.json value → `DEEPSEEK_API_KEY` env var → `.env` (dev mode).
Config lives in %APPDATA%\\SpaceFractionsArchOnly\\config.json — never in the repo, never logged.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from sfagent import APP_NAME

ENV_KEY = "DEEPSEEK_API_KEY"
CONFIG_VERSION = 3  # v2: max_requests 40 → 80, max_total_tokens 2M → 6M; v3: max_steps 60 → 100


@dataclass
class AppConfig:
    api_key: str = ""
    provider: str = "deepseek"  # "deepseek" or "mock"
    thinking: bool = False
    max_steps: int = 100  # agent loop iterations (each step is one LLM request)
    max_requests: int = 80  # LLM calls per run (real runs used 27–57)
    max_cost_usd: float = 1.00
    max_total_tokens: int = 6_000_000  # cumulative; ~98 % are cheap cache hits — the cost cap is the real guard
    max_output_tokens: int = 32768  # a write_files batch of several modules needs more than 8K
    fix_rounds: int = 3  # verify → fix cycles
    ask_before_write: bool = False
    record_deviations: bool = False  # experiment switch: tell the model to record every deviation from the design
    doc_path: str = ""
    profile_path: str = ""  # optional task profile (profiles/*.md)
    view_path: str = ""
    output_dir: str = ""
    config_version: int = CONFIG_VERSION

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def resolved_api_key(self) -> str:
        """Key from config, else environment (including a dev `.env`)."""
        if self.api_key:
            return self.api_key
        load_dotenv_if_present()
        return os.environ.get(ENV_KEY, "")


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_dir() / "config.json"
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(_migrate(data))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return AppConfig()


def _migrate(data: dict) -> dict:
    """Older saved configs kept the old defaults; lift them to the new defaults (user-chosen values are kept)."""
    if int(data.get("config_version", 1)) < 2:
        if data.get("max_requests") == 40:
            data["max_requests"] = 80
        if data.get("max_total_tokens") == 2_000_000:
            data["max_total_tokens"] = 6_000_000
    if int(data.get("config_version", 1)) < 3 and data.get("max_steps") == 60:
        data["max_steps"] = 100
    data["config_version"] = CONFIG_VERSION
    return data


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    path = path or config_dir() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    return path


def mask_key(key: str) -> str:
    """Safe representation for logs/UI: never shows more than the last 4 characters."""
    if not key:
        return "(not set)"
    return "****" + key[-4:] if len(key) > 8 else "****"


def load_dotenv_if_present() -> None:
    """Load `.env` from the working directory or project root (dev mode only, no override)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return
