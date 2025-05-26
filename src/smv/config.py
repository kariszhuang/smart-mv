"""
Constants and configuration settings for the SMV tool.
"""

import os
from typing import Dict, List, Set, Tuple, Any

# LLM Model Settings
MODEL_NAME: str = "gemma3:12b"
OPENAI_API_BASE_URL: str = "http://localhost:11434/v1"
OPENAI_API_KEY: str = "ollama"
MAX_LLM_RETRIES_ON_PARSE_ERROR: int = 3
LLM_TEMPERATURE: float = 0.1
MAX_TOKENS_STEP1: int = 500  # Max tokens for initial decision
MAX_TOKENS_STEP3: int = 500  # Max tokens for candidate/keyword generation
MAX_TOKENS_STEP5: int = 750  # Max tokens for ranking search results
MAX_TOKENS_STEP6: int = 750  # Max tokens for ranking search results
MAX_TOKENS_STEP7: int = 750  # Max tokens for processing results and final suggestion

# File Search and Sorting Settings
MIN_KEYWORD_LENGTH: int = 4
MAX_DEPTH_STEP5: int = 3
HIGH_CONFIDENCE: float = 0.8
MEDIUM_CONFIDENCE: float = 0.5
PATH_PRE_FILTER_THRESHOLD: int = 50
MAX_PATHS_TO_LLM_PREFILTER: int = 150
MAX_PATHS_AFTER_PREFILTER: int = 15
MAX_PATHS_TO_STEP6_LLM: int = 30
MAX_LS_OUTPUT_FILES_TO_SHOW_LLM: int = 10
MAX_LS_OUTPUT_OTHER_FILES: int = 5

# File Processing Settings
ALLOW_LLM_FILE_PROCESSING: bool = True
MAX_FILE_SIZE_FOR_FULL_PROCESSING_MB: int = 10
MAX_EXTRACTED_TEXT_SIZE_KB: int = 100
MIN_MEANINGFUL_TEXT_LENGTH: int = 50

# Image Processing Settings
ALLOW_LLM_IMAGE_PROCESSING: bool = True
MAX_IMAGE_RESOLUTION_FOR_LLM: Tuple[int, int] = (1024, 1024)
IMAGE_QUALITY_FOR_LLM: int = 75

MAX_HINT_RETRIES: int = 2

# File System Settings
IGNORE_HIDDEN_FOLDERS: bool = True

EXCLUDED_DIRS_FIND_PATTERNS: List[str] = [
    ".*",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    "node_modules",
    ".git",
    ".idea",
    ".DS_Store",
    "CVS",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".Spotlight-V100",
    ".fseventsd",
]
# Note: .Trash is not in EXCLUDED_DIRS_FIND_PATTERNS because we might want to search *in* it if specified,
# or it might be a target. The find command itself won't list .Trash unless it's part of search_paths.

FILES_TO_IGNORE_IN_LS: Set[str] = {".DS_Store", "Thumbs.db", ".localized"}

COMMON_FILE_EXTENSIONS_TO_FILTER: Set[str] = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "rtf",
    "odt",
    "ods",
    "odp",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "tiff",
    "webp",
    "svg",
    "mp3",
    "wav",
    "aac",
    "flac",
    "ogg",
    "m4a",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "wmv",
    "flv",
    "webm",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "bz2",
    "tgz",
    "exe",
    "dmg",
    "pkg",
    "deb",
    "rpm",
    "html",
    "htm",
    "css",
    "js",
    "json",
    "xml",
    "yaml",
    "yml",
    "py",
    "java",
    "c",
    "cpp",
    "cs",
    "go",
    "rb",
    "php",
    "swift",
    "kt",
    "srt",
    "vtt",
    "sub",
    "log",
    "ini",
    "cfg",
    "conf",
    "iso",
    "img",
    "md",
}

DELETABLE_CANDIDATE_EXTENSIONS: Set[str] = {
    ".pkg",
    ".dmg",
    ".exe",
    ".msi",
    ".crdownload",
    ".part",
    ".download",
    ".tmp",
    ".temp",
}

# AI Instruction Settings
CUSTOM_AI_INSTRUCTIONS: str = ""

# Special Destination Identifiers
TRASH_DESTINATION_IDENTIFIER: str = "USER_TRASH_BIN"
ARCHIVE_EXTENSIONS: List[str] = [".zip", ".tar", ".gz", ".tgz", ".rar", ".7z", ".bz2"]


# Function to update config at runtime
def update_config(updates: Dict[str, Any]) -> None:
    """
    Update configuration settings at runtime.

    Args:
        updates (dict): Dictionary of configuration settings to update.
    """
    globals().update(updates)


PYPDF_INSTALLED: bool = False
PILLOW_INSTALLED: bool = False
PDF2IMAGE_INSTALLED: bool = False


# Function to check optional dependencies
def check_dependencies() -> Tuple[bool, bool, bool]:
    """
    Check for optional dependencies and return status.

    Returns:
        tuple: (pypdf_installed, pillow_installed, pdf2image_installed)
    """
    # Check for pypdf
    try:
        from pypdf import PdfReader

        pypdf_installed: bool = True
    except ImportError:
        pypdf_installed = False
        print(
            "WARNING: pypdf not installed. PDF text extraction will be disabled. To enable: `pip install pypdf`"
        )

    # Check for Pillow
    try:
        from PIL import Image

        pillow_installed: bool = True
    except ImportError:
        pillow_installed = False
        print(
            "WARNING: Pillow (PIL) not installed. Image processing will be disabled. To enable: `pip install Pillow`"
        )

    # Check for pdf2image
    try:
        from pdf2image import convert_from_path

        pdf2image_installed = True
    except ImportError:
        pdf2image_installed = False
        print(
            "WARNING: pdf2image not installed (or poppler dependency missing). PDF to image conversion will be disabled."
        )

    return pypdf_installed, pillow_installed, pdf2image_installed
