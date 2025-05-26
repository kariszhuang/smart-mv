# 🧠 smart-mv — AI-powered File Organization Tool

`smart-mv` (Smart Move) is an intelligent file organization tool that automatically classifies, renames, and organizes your files based on their **actual contents** — not just filenames. It makes the decision process of "where should this file go?" effortless by analyzing content, context, and your existing folder structure.

## ✅ Key Features

`smart-mv` goes beyond filenames. It reasons like a human:

- **Analyzes textual and visual content** - Extracts and understands text from documents first, then falls back to visual analysis for PDFs and images when needed
- **Matches files with your folder structure** - Finds the perfect location
- **Maintains naming consistency** - Follows existing patterns in target folders
- **Removes clutter** - Identifies disposable files for trash
- **Human-in-the-loop** - Asks for input when uncertain and accepts human hints for better suggestions

## 📥 Installation

You can install smart-mv using pip:

```bash
# Install from PyPI
pip install smart-mv

# Or install directly from GitHub
pip install git+https://github.com/kariszhuang/smart-mv.git
```

## 🚀 Usage

```bash
# Organize a single file
smv /path/to/your/file.pdf

# Get help
smv --help

# Show version
smv -v
```

---

## 🧬 Real-World Example

Model: gemma3:12b

**Before**

```bash
~/Downloads/
├── label.pdf                          # Nike return instructions
├── Document_20250419_0001.pdf         # Scanned passport page
├── HttpToolkit-1.19.3.dmg             # Installer
├── HWSolutions10.2025.pdf             # Handwritten physics equations

~/Documents/Notes/Journals/
└── 2025-05-19.md                      # Markdown journal entry
```

**After:**

```bash
~/Documents/
├── Legal Documents/
│   ├── Receipts/
│   │   └── Nike_Return_Label_1ZXXXXXXXXXXXXXXX.pdf   # Renamed w/ tracking placeholder
│   └── Passport_Page_20250419.pdf                    # Archived passport scan
│
├── School/
│   └── 2025 Spring/
│       └── PHYS 311/
│           └── HW/
│               └── Homework_Solutions/
│                   ├── SolnsHmwk9_2025.pdf           # Existing solution file
│                   └── SolnsHmwk10_2025.pdf          # NEW — Renamed to match pattern
│
└── Notes/
    └── Journals/
        └── 2025-05-19.md                             # Recent journal — left in place

~/.Trash/
└── HttpToolkit-1.19.3.dmg                            # 3 months old installer — moved to Trash
```

e.g.

```bash
$ smv ~/Downloads/HWSolutions10.2025.pdf

Moved:
  From: /Users/<user>/Downloads/HWSolutions10.2025.pdf
    To: /Users/<user>/Documents/School/.../Homework_Solutions/SolnsHmwk10_2025.pdf
```

**Step 1:** Initial assessment notices it's a PDF in Downloads

**Step 2:** Content analysis identifies handwritten equations and diagrams

**Step 3:** Extracts keywords: "solutions, homework, physics, equations"

**Step 4:** Searches folders, finds matching homework solutions directory

**Step 5:** Examines existing files in target location for naming patterns

**Step 6:** Renames file to match pattern, maintaining consistency
