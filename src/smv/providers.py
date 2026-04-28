"""
Provider registry and model discovery helpers for SMV.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Dict, List, Optional, Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    display_name: str
    default_model: str
    default_base_url: Optional[str]
    api_key_required: bool
    api_key_env_vars: Tuple[str, ...]
    default_api_key: Optional[str] = None
    model_suggestions: Tuple[str, ...] = ()


PROVIDER_ORDER: Tuple[str, ...] = ("ollama", "openai", "anthropic", "gemini")

PROVIDERS: Dict[str, ProviderSpec] = {
    "ollama": ProviderSpec(
        id="ollama",
        display_name="Ollama",
        default_model="gemma3:12b",
        default_base_url="http://localhost:11434/v1",
        api_key_required=False,
        api_key_env_vars=("OLLAMA_API_KEY",),
        default_api_key="ollama",
        model_suggestions=("gemma3:12b", "qwen3:8b", "llama3.1:8b"),
    ),
    "openai": ProviderSpec(
        id="openai",
        display_name="OpenAI",
        default_model="gpt-4.1-mini",
        default_base_url="https://api.openai.com/v1",
        api_key_required=True,
        api_key_env_vars=("OPENAI_API_KEY",),
        model_suggestions=("gpt-4.1-mini", "gpt-4.1", "gpt-5-mini"),
    ),
    "anthropic": ProviderSpec(
        id="anthropic",
        display_name="Anthropic",
        default_model="claude-3-5-sonnet-latest",
        default_base_url=None,
        api_key_required=True,
        api_key_env_vars=("ANTHROPIC_API_KEY",),
        model_suggestions=(
            "claude-3-5-sonnet-latest",
            "claude-3-7-sonnet-latest",
            "claude-3-5-haiku-latest",
        ),
    ),
    "gemini": ProviderSpec(
        id="gemini",
        display_name="Google Gemini",
        default_model="gemini-2.5-flash",
        default_base_url=None,
        api_key_required=True,
        api_key_env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        model_suggestions=("gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"),
    ),
}


def get_provider(provider_id: str) -> ProviderSpec:
    normalized = (provider_id or "ollama").strip().lower()
    if normalized not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider_id}'")
    return PROVIDERS[normalized]


def ordered_providers() -> List[ProviderSpec]:
    return [PROVIDERS[p_id] for p_id in PROVIDER_ORDER]


def provider_ids() -> List[str]:
    return [provider.id for provider in ordered_providers()]


def _normalize_ollama_tags_url(base_url: Optional[str]) -> str:
    url = base_url or PROVIDERS["ollama"].default_base_url or "http://localhost:11434/v1"
    parsed = urllib_parse.urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or "localhost:11434"
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[: -len("/v1")]
    if not path:
        path = ""
    return urllib_parse.urlunparse((scheme, netloc, f"{path}/api/tags", "", "", ""))


def _list_ollama_models(base_url: Optional[str], timeout: int) -> List[str]:
    url = _normalize_ollama_tags_url(base_url)
    with urllib_request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    models = []
    for model_info in data.get("models", []):
        name = model_info.get("name")
        if name:
            models.append(str(name))
    return sorted(set(models))


def list_models(
    provider_id: str,
    base_url: Optional[str] = None,
    timeout: int = 4,
) -> List[str]:
    provider = get_provider(provider_id)
    models: List[str] = []

    if provider.id == "ollama":
        try:
            models = _list_ollama_models(base_url, timeout)
        except (urllib_error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            models = []

    merged = list(models)
    for suggested in provider.model_suggestions:
        if suggested not in merged:
            merged.append(suggested)
    return merged
