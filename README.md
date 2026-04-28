# smart-mv

`smart-mv` helps you clean up messy folders by looking at what a file actually is, then suggesting the right place, the right name, or when it should just go to Trash.

Instead of sorting by filename alone, it uses file content, folder context, and your existing naming patterns so your files end up where they already make sense.

## Why People Use It

- Turn a chaotic `Downloads` folder into an organized system
- Rename vague files like `Document_20250419_0001.pdf` into something useful
- Match the naming style already used in your folders
- Catch old installers and obvious clutter before they pile up
- Keep you in control when the choice is not obvious

## Quick Start

```bash
pip install smart-mv
smv ai setup
smv /path/to/file.pdf
```

If you use local models, `Ollama` is supported. OpenAI, Anthropic, and Gemini are also available.

## What It Handles

- PDFs
- DOCX files
- Text files
- Images
- Common clutter like old installers and temporary downloads

## Demo 1: Homework PDF sorted and renamed

**Before**

```text
~/Downloads/
└── HWSolutions10.2025.pdf

~/Documents/School/2025 Spring/PHYS 311/HW/Homework_Solutions/
└── SolnsHmwk9_2025.pdf
```

**After**

```text
~/Documents/School/2025 Spring/PHYS 311/HW/Homework_Solutions/
├── SolnsHmwk9_2025.pdf
└── SolnsHmwk10_2025.pdf
```

`smart-mv` reads the file, figures out it is a physics homework solution set, finds the matching course folder, and renames it to fit the pattern already used there.

## Demo 2: Downloads folder cleanup

**Before**

```text
~/Downloads/
├── label.pdf
├── Document_20250419_0001.pdf
└── HttpToolkit-1.19.3.dmg
```

**After**

```text
~/Documents/
├── Legal Documents/
│   ├── Passport_Page_20250419.pdf
│   └── Receipts/
│       └── Nike_Return_Label_1ZXXXXXXXXXXXXXXX.pdf

~/.Trash/
└── HttpToolkit-1.19.3.dmg
```

The return label gets renamed clearly, the passport scan is archived somewhere sensible, and the old installer is treated like clutter instead of living in `Downloads` forever.

## Basic Commands

```bash
# Organize a file
smv /path/to/file.pdf

# Same thing, explicit form
smv sort /path/to/file.pdf

# Set up or change your AI provider
smv ai setup

# See current AI settings
smv ai show
```

## Install From Source

```bash
git clone https://github.com/kariszhuang/smart-mv.git
cd smart-mv
pip install -e .
smv --version
```

## Python Version

Python `3.10+`
