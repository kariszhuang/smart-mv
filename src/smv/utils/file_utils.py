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


def get_file_age_days(file_path: str) -> Optional[int]:
    """
    Get file age in whole days.

    Args:
        file_path (str): Path to the file.

    Returns:
        Optional[int]: Age in days or None if unavailable.
    """
    try:
        mtime = os.path.getmtime(file_path)
        file_mtime_dt = datetime.datetime.fromtimestamp(mtime)
        now_dt = datetime.datetime.now()
        return max((now_dt - file_mtime_dt).days, 0)
    except Exception as e:
        print(f"Could not get file age in days for {file_path}: {e}")
        return None


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


import concurrent.futures
import subprocess


def fast_find(search_paths: List[str], keywords_str: str, find_type: str = "d", max_depth: int = 3, excluded_patterns: List[str] = None) -> List[str]:
    """
    Fast concurrent search using `fd` (rust) if available, falling back to os.scandir.
    """
    if excluded_patterns is None:
        from smv import config
        excluded_patterns = config.EXCLUDED_DIRS_FIND_PATTERNS

    keywords = [kw.strip().lower() for kw in keywords_str.split(',')] if keywords_str else []
    results = set()

    fd_bin = shutil.which("fdfind") or shutil.which("fd")
    if fd_bin:
        for p in search_paths:
            if not os.path.isdir(p): continue
            cmd = [fd_bin, "--type", find_type, "--absolute-path", "--color", "never", "--hidden"]
            if max_depth is not None and max_depth >= 0:
                cmd.extend(["--max-depth", str(max_depth)])
            for ex in excluded_patterns:
                cmd.extend(["--exclude", ex])
            cmd.append("--")
            if keywords:
                cmd.append(".*(" + "|".join(keywords) + ").*")
            else:
                cmd.append(".*")
            cmd.append(p)
            try:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if line.strip():
                            if find_type == "f":
                                results.add(os.path.dirname(os.path.normpath(line.strip())))
                            else:
                                results.add(os.path.normpath(line.strip()))
            except Exception:
                pass
        if results:
            return list(results)

    def scan_dir(path: str, current_depth: int):
        if max_depth is not None and current_depth > max_depth:
            return
        try:
            with os.scandir(path) as it:
                for entry in it:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    if is_dir and any(ex in entry.name for ex in excluded_patterns):
                        continue

                    if (find_type == "d" and is_dir) or (find_type == "f" and entry.is_file(follow_symlinks=False)):
                        match = not keywords or any(kw in entry.name.lower() for kw in keywords)
                        if match:
                            if find_type == "f":
                                results.add(os.path.dirname(os.path.normpath(entry.path)))
                            else:
                                results.add(os.path.normpath(entry.path))

                    if is_dir:
                        scan_dir(entry.path, current_depth + 1)
        except PermissionError:
            pass

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(scan_dir, p, 1) for p in search_paths if os.path.isdir(p)]
        concurrent.futures.wait(futures)

    return list(results)


def get_sample_files(folder_path: str, max_samples: int = 3) -> List[str]:
    """Get a few sample files from a directory to help LLM context."""
    samples = []
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and not entry.name.startswith('.'):
                    samples.append(entry.name)
                    if len(samples) >= max_samples:
                        break
    except Exception:
        pass
    return samples
