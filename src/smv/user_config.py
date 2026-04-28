"""
Persistent user AI configuration and API key storage helpers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from smv import providers

KEYRING_SERVICE = "smart-mv"


def _config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "smv"
    return Path.home() / ".config" / "smv"


def get_config_path() -> Path:
    return _config_dir() / "config.json"


def _default_config() -> Dict[str, Any]:
    ollama = providers.get_provider("ollama")
    return {
        "provider": ollama.id,
        "model": ollama.default_model,
        "base_url": ollama.default_base_url,
        "api_key_storage": "keyring",
        "api_key": None,
    }


def ensure_config_dir() -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)


def load_user_config() -> Dict[str, Any]:
    path = get_config_path()
    config = _default_config()
    if not path.exists():
        return config

    try:
        with path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return config

    if isinstance(loaded, dict):
        config.update(loaded)
    return config


def save_user_config(config: Dict[str, Any]) -> None:
    ensure_config_dir()
    path = get_config_path()
    with path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _load_keyring():
    try:
        import keyring

        return keyring
    except ImportError:
        return None


def _env_api_key(provider: providers.ProviderSpec) -> Optional[str]:
    for env_name in provider.api_key_env_vars:
        value = os.environ.get(env_name)
        if value:
            return value
    return None


def _read_keyring_api_key(provider_id: str) -> Optional[str]:
    keyring = _load_keyring()
    if keyring is None:
        return None

    try:
        return keyring.get_password(KEYRING_SERVICE, provider_id)
    except Exception:
        return None


def get_api_key(config: Dict[str, Any]) -> Optional[str]:
    provider = providers.get_provider(config.get("provider", "ollama"))

    env_key = _env_api_key(provider)
    if env_key:
        return env_key

    storage_mode = config.get("api_key_storage", "keyring")
    if storage_mode == "keyring":
        keyring_key = _read_keyring_api_key(provider.id)
        if keyring_key:
            return keyring_key

    plain_key = config.get("api_key")
    if plain_key:
        return str(plain_key)

    return provider.default_api_key


def set_api_key(
    config: Dict[str, Any],
    api_key: str,
    storage: str = "keyring",
    allow_plaintext_fallback: bool = True,
) -> str:
    normalized_storage = storage.strip().lower()
    provider_id = providers.get_provider(config.get("provider", "ollama")).id

    if normalized_storage == "plaintext":
        config["api_key_storage"] = "plaintext"
        config["api_key"] = api_key
        save_user_config(config)
        return "plaintext"

    keyring = _load_keyring()
    if keyring is None:
        if not allow_plaintext_fallback:
            raise RuntimeError(
                "keyring is not available and plaintext fallback is disabled."
            )
        config["api_key_storage"] = "plaintext"
        config["api_key"] = api_key
        save_user_config(config)
        return "plaintext"

    try:
        keyring.set_password(KEYRING_SERVICE, provider_id, api_key)
        config["api_key_storage"] = "keyring"
        config["api_key"] = None
        save_user_config(config)
        return "keyring"
    except Exception:
        if not allow_plaintext_fallback:
            raise
        config["api_key_storage"] = "plaintext"
        config["api_key"] = api_key
        save_user_config(config)
        return "plaintext"


def get_effective_ai_config() -> Dict[str, Any]:
    raw_config = load_user_config()
    provider = providers.get_provider(raw_config.get("provider", "ollama"))
    model_name = raw_config.get("model") or provider.default_model
    base_url = raw_config.get("base_url")
    if not base_url:
        base_url = provider.default_base_url

    merged = dict(raw_config)
    merged["provider"] = provider.id
    merged["model"] = model_name
    merged["base_url"] = base_url
    merged["api_key"] = get_api_key(merged)
    return merged
