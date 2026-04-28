# smart-mv

`smart-mv` (`smv`) is an AI-powered file organizer that analyzes file content and suggests where to move files, how to rename them, and when to trash clutter.

## Highlights

- **Multi-provider AI setup** with persistent profile:
  - **Ollama** (first in selection list)
  - OpenAI
  - Anthropic
  - Google Gemini
- **Model selection** per provider (with Ollama local model discovery).
- **API key persistence** with OS keyring and explicit plaintext fallback.
- **Faster sorting flow** with deterministic trash shortcuts and depth-limited search.
- **Provider/model settings can be changed anytime** from CLI.

## Quick start (uv-first)

### Install

```bash
uv tool install smart-mv
```

or from source:

```bash
git clone https://github.com/kariszhuang/smart-mv.git
cd smart-mv
uv sync
uv run smv --version
```

### Configure AI once

```bash
uv run smv ai setup
```

This interactive setup lets you choose provider, model, base URL (where applicable), and API key storage.

### Organize a file

```bash
uv run smv /path/to/file.pdf
```

## AI configuration commands

```bash
# Show current profile
uv run smv ai show

# Interactive reconfiguration
uv run smv ai setup

# Set provider/model/base URL directly
uv run smv ai set-provider ollama
uv run smv ai set-model gemma3:12b
uv run smv ai set-base-url http://localhost:11434/v1

# Set API key (keyring by default; falls back to plaintext if needed)
uv run smv ai set-api-key --storage keyring

# List suggested/discovered models
uv run smv ai list-models --provider ollama
```

## Development

```bash
uv sync
uv run python -m unittest discover -s tests -q
```

## Python version

This project now targets **Python 3.10+**.
