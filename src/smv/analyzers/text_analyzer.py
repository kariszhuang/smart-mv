"""
Text analyzer functionality for SMV.
"""

import os
import zipfile
import xml.etree.ElementTree as ET
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
    def extract_from_docx(file_path: str, max_size_kb: int = 100) -> Tuple[bool, str]:
        """
        Extract text from a DOCX file by reading WordprocessingML XML parts.

        Args:
            file_path (str): Path to the DOCX file.
            max_size_kb (int): Maximum size of extracted text in KB.

        Returns:
            Tuple[bool, str]: (success, extracted_text)
        """
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        max_bytes = max_size_kb * 1024
        extracted_parts = []
        current_size = 0

        def append_text(text: str) -> bool:
            nonlocal current_size
            if not text:
                return True
            encoded = text.encode("utf-8")
            remaining = max_bytes - current_size
            if remaining <= 0:
                return False
            if len(encoded) > remaining:
                truncated = encoded[:remaining].decode("utf-8", errors="ignore").strip()
                if truncated:
                    extracted_parts.append(truncated)
                extracted_parts.append(f"...(truncated at {max_size_kb}KB limit)...")
                current_size = max_bytes
                return False

            extracted_parts.append(text)
            current_size += len(encoded)
            return True

        try:
            with zipfile.ZipFile(file_path) as docx_zip:
                zip_names = set(docx_zip.namelist())
                if "word/document.xml" not in zip_names:
                    return False, "Invalid DOCX: missing word/document.xml"

                ordered_parts = ["word/document.xml"]
                ordered_parts.extend(
                    sorted(
                        name
                        for name in zip_names
                        if name.startswith("word/header") and name.endswith(".xml")
                    )
                )
                ordered_parts.extend(
                    sorted(
                        name
                        for name in zip_names
                        if name.startswith("word/footer") and name.endswith(".xml")
                    )
                )
                ordered_parts.extend(
                    name
                    for name in ("word/footnotes.xml", "word/endnotes.xml")
                    if name in zip_names
                )

                stop_extraction = False
                for part_name in ordered_parts:
                    if part_name not in zip_names:
                        continue

                    with docx_zip.open(part_name) as xml_file:
                        xml_content = xml_file.read()

                    try:
                        root = ET.fromstring(xml_content)
                    except ET.ParseError:
                        continue

                    if part_name != "word/document.xml":
                        if not append_text(f"[{os.path.basename(part_name)}]"):
                            stop_extraction = True
                            break

                    for paragraph in root.findall(".//w:p", namespaces):
                        text_runs = []
                        for text_node in paragraph.findall(".//w:t", namespaces):
                            if text_node.text:
                                text_runs.append(text_node.text)
                        paragraph_text = "".join(text_runs).strip()
                        if paragraph_text and not append_text(paragraph_text):
                            stop_extraction = True
                            break

                    if stop_extraction:
                        break

            if not extracted_parts:
                return False, "No text extracted from DOCX"

            return True, "\n\n".join(extracted_parts)

        except zipfile.BadZipFile:
            return False, "Invalid DOCX file (not a readable ZIP package)"
        except Exception as e:
            return False, f"Error extracting text from DOCX: {str(e)}"

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
