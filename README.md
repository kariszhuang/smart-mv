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
- **Richer document understanding** with native `.docx` text extraction.
- **Filesystem tool-calling (OpenAI/Ollama)** so AI can list directories and find files/folders during destination planning.

## Quick start

### Install

```bash
pip install smart-mv
```

or from source:

```bash
git clone https://github.com/kariszhuang/smart-mv.git
cd smart-mv
pip install -e .
smv --version
```

### Configure AI once

```bash
smv ai setup
```

This interactive setup lets you choose provider, model, base URL (where applicable), and API key storage.

### Organize a file

```bash
smv /path/to/file.pdf
```

## AI configuration commands

```bash
# Show current profile
smv ai show

# Interactive reconfiguration
smv ai setup

# Set provider/model/base URL directly
smv ai set-provider ollama
smv ai set-model gemma3:12b
smv ai set-base-url http://localhost:11434/v1

# Set API key (keyring by default; falls back to plaintext if needed)
smv ai set-api-key --storage keyring

# List suggested/discovered models
smv ai list-models --provider ollama
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -q
```

## Python version

This project now targets **Python 3.10+**.
