"""
File utility functions for SMV.
"""

import os
import shutil
import hashlib
import datetime
from typing import Optional, Tuple, List


def get_file_age_description(file_path: str) -> str:
    """
    Get a human-readable description of file age.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: Human-readable description of file age.
    """
    try:
        mtime = os.path.getmtime(file_path)
        file_mtime_dt = datetime.datetime.fromtimestamp(mtime)
        now_dt = datetime.datetime.now()
        delta = now_dt - file_mtime_dt

        if delta.days == 0:
            if delta.seconds < 60:
                return "modified just now"
            if delta.seconds < 3600:
                return f"modified {delta.seconds // 60} minutes ago"
            return f"modified {delta.seconds // 3600} hours ago"
        elif delta.days == 1:
            return "modified yesterday"
        elif delta.days < 7:
            return f"modified {delta.days} days ago"
        elif delta.days < 30:
            return f"modified approx. {delta.days // 7} weeks ago"
        elif delta.days < 365:
            return f"modified approx. {delta.days // 30} months ago"
        else:
            return f"modified approx. {delta.days // 365} years ago"
    except Exception as e:
        print(f"Could not get file age for {file_path}: {e}")
        return "age unknown"


def are_files_identical(file1_path: str, file2_path: str) -> bool:
    """
    Compare two files for identical content using MD5 hashing.

    Args:
        file1_path (str): Path to first file.
        file2_path (str): Path to second file.

    Returns:
        bool: True if files are identical, False otherwise.
    """
    try:
        hash1 = hashlib.md5()
        hash2 = hashlib.md5()

        with open(file1_path, "rb") as f1:
            for chunk in iter(lambda: f1.read(4096), b""):
                hash1.update(chunk)

        with open(file2_path, "rb") as f2:
            for chunk in iter(lambda: f2.read(4096), b""):
                hash2.update(chunk)

        return hash1.hexdigest() == hash2.hexdigest()
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False


def check_if_archive_extracted(
    archive_path: str, archive_extensions: Optional[List[str]] = None
) -> Optional[str]:
    """
    Check if an archive file appears to have been extracted in the same directory.

    Args:
        archive_path (str): Path to the archive file.
        archive_extensions (Optional[List[str]], optional): List of archive file extensions. If None, uses default from config.

    Returns:
        Optional[str]: Path to the extracted folder if found, None otherwise.
    """
    # Import here to avoid circular imports
    from smv import config

    # Use provided extensions or default from config
    if archive_extensions is None:
        archive_extensions = config.ARCHIVE_EXTENSIONS
    _, archive_ext = os.path.splitext(archive_path)
    archive_ext = archive_ext.lower()

    if archive_ext not in archive_extensions:
        return None

    archive_basename_no_ext = os.path.basename(archive_path)
    for ext_part in sorted(archive_extensions, key=len, reverse=True):
        if archive_basename_no_ext.lower().endswith(ext_part):
            archive_basename_no_ext = archive_basename_no_ext[: -len(ext_part)]
            break

    if not archive_basename_no_ext:
        return None

    parent_dir = os.path.dirname(archive_path)
    potential_extracted_folder_path = os.path.join(parent_dir, archive_basename_no_ext)

    if os.path.isdir(potential_extracted_folder_path):
        # Check if folder modification time is >= archive mod time, indicating extraction happened
        try:
            archive_mtime = os.path.getmtime(archive_path)
            folder_mtime = os.path.getmtime(potential_extracted_folder_path)
            if folder_mtime >= archive_mtime:
                return potential_extracted_folder_path
        except Exception:
            # If we can't check times, at least return the folder as a candidate
            return potential_extracted_folder_path
    return None


def execute_move(
    source_path: str, destination_path: str, trash_dir: Optional[None] = None
) -> Tuple[bool, str]:
    """
    Execute file move operation with error handling.

    Args:
        source_path (str): Path to the source file.
        destination_path (str): Path to the destination location.
        trash_dir (str): Path to the trash directory.

    Returns:
        Tuple[bool, str]: (success status, message)
    """
    try:
        destination_dir = os.path.dirname(destination_path)

        # Create destination directory if it doesn't exist
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir, exist_ok=True)

        # Check if destination file exists
        if os.path.exists(destination_path):
            if are_files_identical(source_path, destination_path):
                # If destination already has identical file, move source to trash
                if trash_dir:
                    trash_destination = os.path.join(
                        trash_dir, os.path.basename(source_path)
                    )
                    counter = 1
                    temp_base, temp_ext = os.path.splitext(trash_destination)

                    while os.path.exists(trash_destination):
                        trash_destination = f"{temp_base}_{counter}{temp_ext}"
                        counter += 1

                    shutil.move(source_path, trash_destination)
                    return (
                        True,
                        f"Source file identical to destination. Moved to trash: {trash_destination}",
                    )
                else:
                    os.remove(source_path)
                    return (
                        True,
                        "Source file identical to destination. Removed source file.",
                    )
            else:
                return (
                    False,
                    "Destination exists with different content. Move aborted to prevent overwrite.",
                )

        # Execute the move
        shutil.move(source_path, destination_path)
        return True, f"Successfully moved file to {destination_path}"

    except Exception as e:
        return False, f"Error moving file: {str(e)}"
