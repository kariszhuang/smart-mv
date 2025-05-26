"""
Image analyzer functionality for SMV.
"""

import os
import base64
from io import BytesIO
from typing import Tuple, Optional, List


class ImageAnalyzer:
    """Handles image processing and analysis."""

    @staticmethod
    def is_image_file(file_path: str) -> bool:
        """
        Determine if a file is an image based on extension.

        Args:
            file_path (str): Path to the file.

        Returns:
            bool: True if the file is an image, False otherwise.
        """
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".svg",
            ".ico",
            ".heic",
            ".heif",
        }

        _, ext = os.path.splitext(file_path)
        return ext.lower() in image_extensions

    @staticmethod
    def process_image(
        image_path: str,
        max_resolution: Tuple[int, int] = (1024, 1024),
        quality: int = 75,
    ) -> Optional[str]:
        """
        Process an image file by resizing and compressing it, returning base64 string.

        Args:
            image_path (str): Path to the image file.
            max_resolution (Tuple[int, int]): Maximum width and height.
            quality (int): JPEG compression quality (1-100).

        Returns:
            Optional[str]: Base64 encoded image string or None if processing failed.
        """
        try:
            from PIL import Image
        except ImportError:
            print("Pillow (PIL) not installed")
            return None

        try:
            # Open the image
            img = Image.open(image_path)

            # Convert RGBA to RGB if needed (for JPEG compatibility)
            if img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = rgb_img

            # Resize if needed
            if img.width > max_resolution[0] or img.height > max_resolution[1]:
                img.thumbnail(max_resolution, Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality)

            # Convert to base64
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

            print(f"Image processed: {img.width}x{img.height}")
            return base64_str

        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return None

    @staticmethod
    def extract_image_metadata(image_path: str) -> dict:
        """
        Extract metadata from an image file.

        Args:
            image_path (str): Path to the image file.

        Returns:
            dict: Dictionary with image metadata.
        """
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
        except ImportError:
            return {"error": "Pillow (PIL) not installed"}

        try:
            # Open the image
            img = Image.open(image_path)

            # Basic metadata
            metadata = {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
            }

            # Extract EXIF data if available
            try:
                exif_data = img.getexif()
                if exif_data:
                    exif = {
                        TAGS.get(tag_id, tag_id): value
                        for tag_id, value in exif_data.items()
                    }

                    # Add selected EXIF data that might be useful
                    exif_selection = {}
                    for tag in ["DateTimeOriginal", "Make", "Model", "Orientation"]:
                        if tag in exif:
                            exif_selection[tag] = str(exif[tag])

                    if exif_selection:
                        metadata["exif"] = exif_selection
            except (AttributeError, TypeError, ValueError):
                # Not all image formats have EXIF data
                pass

            return metadata

        except Exception as e:
            return {"error": f"Error extracting image metadata: {str(e)}"}

    @staticmethod
    def convert_to_base64(image_bytes: bytes) -> str:
        """
        Convert image bytes to base64 string.

        Args:
            image_bytes (bytes): Raw image bytes.

        Returns:
            str: Base64 encoded string.
        """
        return base64.b64encode(image_bytes).decode("utf-8")

    @staticmethod
    def get_image_description(metadata: dict) -> str:
        """
        Generate a human-readable description of an image from its metadata.

        Args:
            metadata (dict): Image metadata.

        Returns:
            str: Human-readable description.
        """
        if "error" in metadata:
            return f"Image analysis error: {metadata['error']}"

        parts = []

        # Basic image info
        if "format" in metadata and "size" in metadata:
            width, height = metadata["size"]
            parts.append(f"{metadata['format']} image, {width}x{height} pixels")

        # Add camera info if available
        if "exif" in metadata:
            exif = metadata["exif"]
            if "Make" in exif and "Model" in exif:
                parts.append(f"Taken with {exif['Make']} {exif['Model']}")
            if "DateTimeOriginal" in exif:
                parts.append(f"Date: {exif['DateTimeOriginal']}")

        return ", ".join(parts)

    @staticmethod
    def pdf_to_image(
        pdf_path: str,
        max_resolution: Tuple[int, int] = (1024, 1024),
        quality: int = 75,
        page: int = 1,
    ) -> Optional[str]:
        """
        Convert the first page of a PDF to an image and return as base64.

        Args:
            pdf_path (str): Path to the PDF file.
            max_resolution (Tuple[int, int]): Maximum width and height.
            quality (int): JPEG compression quality (1-100).
            page (int): Page number to extract (1-based).

        Returns:
            Optional[str]: Base64 encoded image string or None if conversion failed.
        """
        try:
            from pdf2image import convert_from_path
            from PIL import Image
        except ImportError:
            print("Required libraries not installed (pdf2image or pillow)")
            return None

        try:
            # Convert PDF page to image
            images = convert_from_path(
                pdf_path,
                first_page=page,
                last_page=page,
                dpi=150,
                timeout=10,
            )

            if not images:
                print(f"No images extracted from PDF: {pdf_path}")
                return None

            # Process the image
            img = images[0]

            # Convert RGBA to RGB if needed
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            # Resize if needed
            if img.width > max_resolution[0] or img.height > max_resolution[1]:
                img.thumbnail(max_resolution, Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality)

            # Convert to base64
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

            print(f"Successfully converted page {page} of PDF to image")
            return base64_str

        except Exception as e:
            print(f"Error converting PDF to image: {e}")
            return None
