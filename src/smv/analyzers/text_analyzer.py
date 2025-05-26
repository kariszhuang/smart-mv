"""
Text analyzer functionality for SMV.
"""

import os
import base64
from typing import Tuple, Optional


class TextAnalyzer:
    """Handles text extraction from various file types."""

    @staticmethod
    def extract_from_pdf(file_path: str, max_size_kb: int = 100) -> Tuple[bool, str]:
        """
        Extract text from a PDF file.

        Args:
            file_path (str): Path to the PDF file.
            max_size_kb (int): Maximum size of extracted text in KB.

        Returns:
            Tuple[bool, str]: (success, extracted_text)
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            return False, "pypdf not installed"

        try:
            reader = PdfReader(file_path)
            text_parts = []
            current_size = 0
            max_bytes = max_size_kb * 1024

            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    part_with_header = f"[Page {page_num + 1}]: {page_text}"
                    text_parts.append(part_with_header)
                    current_size += len(part_with_header.encode("utf-8"))

                    if current_size >= max_bytes:
                        text_parts.append(f"...(truncated at {max_size_kb}KB limit)...")
                        break

            if not text_parts:
                return False, "No text extracted from PDF"

            extracted_text = "\n\n".join(text_parts)
            return True, extracted_text

        except Exception as e:
            return False, f"Error extracting text from PDF: {str(e)}"

    @staticmethod
    def convert_pdf_to_images(file_path: str, max_pages: int = 2) -> Tuple[bool, list]:
        """
        Convert pages of a PDF to images.

        Args:
            file_path (str): Path to the PDF file.
            max_pages (int): Maximum number of pages to convert.

        Returns:
            Tuple[bool, list]: (success, list_of_images)
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            return False, ["pdf2image not installed"]

        try:
            images = convert_from_path(file_path, first_page=1, last_page=max_pages)
            return True, images
        except Exception as e:
            return False, [f"Error converting PDF to image: {str(e)}"]

    @staticmethod
    def get_file_type_description(file_path: str) -> str:
        """
        Get a description of the file type.

        Args:
            file_path (str): Path to the file.

        Returns:
            str: Description of the file type.
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Add file type detection logic here
        file_type_map = {
            ".pdf": "PDF document",
            ".docx": "Word document",
            ".xlsx": "Excel spreadsheet",
            ".pptx": "PowerPoint presentation",
            ".txt": "Text file",
            ".csv": "CSV (Comma-separated values) file",
            ".json": "JSON file",
            ".xml": "XML file",
            ".html": "HTML file",
            ".md": "Markdown file",
            ".py": "Python source code",
            ".js": "JavaScript source code",
            ".cpp": "C++ source code",
            ".java": "Java source code",
            ".sh": "Shell script",
            ".zip": "ZIP archive",
            ".tar.gz": "Compressed TAR archive",
            ".gz": "Gzip compressed file",
            ".7z": "7-Zip archive",
            ".jpg": "JPEG image",
            ".png": "PNG image",
            ".gif": "GIF image",
            ".svg": "SVG image",
            ".mp3": "MP3 audio file",
            ".mp4": "MP4 video file",
            ".mov": "QuickTime video file",
            ".exe": "Windows executable",
            ".dmg": "macOS disk image",
            ".pkg": "macOS installer package",
        }

        # Check for combined extensions like .tar.gz
        if file_path.lower().endswith(".tar.gz"):
            return file_type_map.get(".tar.gz", "Compressed TAR archive")

        return file_type_map.get(ext, f"{ext[1:].upper() if ext else 'Unknown'} file")

    @staticmethod
    def is_text_file(file_path: str) -> bool:
        """
        Determine if a file is likely a text file.

        Args:
            file_path (str): Path to the file.

        Returns:
            bool: True if the file is likely a text file, False otherwise.
        """
        text_extensions = {
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".srt",
            ".xml",
            ".yaml",
            ".yml",
            ".html",
            ".htm",
            ".css",
            ".js",
            ".py",
            ".java",
            ".c",
            ".cpp",
            ".cs",
            ".go",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".sh",
            ".bash",
            ".zsh",
            ".bat",
            ".ps1",
            ".conf",
            ".cfg",
            ".ini",
            ".log",
            ".sql",
            ".r",
            ".scala",
        }

        _, ext = os.path.splitext(file_path)
        if ext.lower() in text_extensions:
            return True

        # Try to read the file as text
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sample = f.read(4096)  # Read first 4KB
                # If we read something and it doesn't have too many non-ASCII chars, consider it text
                if (
                    sample
                    and sum(c > 127 for c in sample.encode("utf-8")) < len(sample) * 0.3
                ):
                    print(f"File {file_path} is likely a text file.")
                    return True
        except (UnicodeDecodeError, IOError):
            return False

        return False

    @staticmethod
    def extract_from_text_file(
        file_path: str, max_size_kb: int = 100
    ) -> Tuple[bool, str]:
        """
        Extract content from a text file with size limits.

        Args:
            file_path (str): Path to the text file.
            max_size_kb (int): Maximum size of extracted text in KB.

        Returns:
            Tuple[bool, str]: (success, extracted_text)
        """
        try:
            max_bytes = max_size_kb * 1024

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes + 1)

            if len(content.encode("utf-8")) > max_bytes:
                content = content[: max_bytes // 2]  # Truncate to be safe
                content += f"\n\n...(truncated at {max_size_kb}KB limit)..."

            return True, content
        except Exception as e:
            return False, f"Error reading text file: {str(e)}"
