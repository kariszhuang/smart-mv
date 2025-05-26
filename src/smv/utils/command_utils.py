"""
Command utility functions for SMV.
"""

import os
import subprocess
from typing import List, Optional, Tuple
import os


def run_shell_command(
    command_parts: List[str],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Run a shell command and return its output.

    Args:
        command_parts (List[str]): Command and its arguments as a list.

    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command_parts,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit
        )
        success = result.returncode == 0
        return success, result.stdout, result.stderr
    except FileNotFoundError:
        error_msg = f"Command not found: {command_parts[0]}"
        print(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Error running command {' '.join(command_parts)}: {str(e)}"
        print(error_msg)
        return False, None, error_msg


def build_find_command(
    search_paths: List[str],
    keyword_conditions: List[str],
    excluded_patterns: List[str],
    ignore_hidden: bool = True,
    find_type: str = "f",
    print0: bool = False,
) -> List[str]:
    """
    Build a Unix find command with exclusions and conditions.

    Args:
        search_paths (List[str]): Paths to search in.
        keyword_conditions (List[str]): Search conditions for find.
        excluded_patterns (List[str]): Directory patterns to exclude.
        ignore_hidden (bool): Whether to ignore hidden directories.
        find_type (str): Type of items to find ('f' for files, 'd' for directories).
        print0 (bool): Whether to use null character as separator.

    Returns:
        List[str]: Command parts for the find command.
    """
    cmd = ["find"]
    valid_search_paths = [p for p in search_paths if p]
    if not valid_search_paths:
        return []
    cmd.extend(valid_search_paths)

    prune_expr = []
    current_excluded_patterns = list(excluded_patterns)

    # Handle hidden folders based on setting
    if ignore_hidden and ".*" not in current_excluded_patterns:
        current_excluded_patterns.append(".*")
    elif not ignore_hidden and ".*" in current_excluded_patterns:
        current_excluded_patterns.remove(".*")

    # Build prune expressions for each pattern
    for i, pattern in enumerate(current_excluded_patterns):
        if i == 0:
            prune_expr.extend(["-path", f"*/{pattern}", "-prune"])
        else:
            prune_expr.extend(["-o", "-path", f"*/{pattern}", "-prune"])

    # Add pruning to the command if patterns exist
    if prune_expr:
        cmd.append("(")
        cmd.extend(prune_expr)
        cmd.extend(["-o", "-type", find_type])
    else:
        cmd.extend(["-type", find_type])

    # Add keyword conditions if any
    if keyword_conditions:
        if not prune_expr:
            cmd.append("(")
        else:
            cmd.append("-a")
            cmd.append("(")
        cmd.extend(keyword_conditions)
        cmd.append(")")

    # Add print option
    cmd.append("-print0" if print0 else "-print")

    return cmd


def build_keyword_options(keywords_str: str) -> List[str]:
    """
    Build command line options for keyword search.

    Args:
        keywords_str (str): Comma-separated list of keywords.

    Returns:
        List[str]: Command line arguments for the find command.
    """
    options: List[str] = []
    if not keywords_str:
        return options

    keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    for i, kw in enumerate(keywords):
        if i > 0:
            options.append("-o")
        options.extend(["-iname", f"*{kw}*"])
    return options


def build_find_command_parts(
    search_paths: List[str],
    keyword_conditions: List[str],
    find_type: str = "f",
    excluded_patterns: Optional[List[str]] = None,
    print0: bool = False,
) -> List[str]:
    """
    Build a find command for searching files or directories.

    Args:
        search_paths (List[str]): Paths to search in.
        keyword_conditions (List[str]): Keyword search conditions.
        find_type (str): Type of item to find ('f' for files, 'd' for directories).
        excluded_patterns (Optional[List[str]]): Patterns to exclude.
        print0 (bool): Whether to use null terminators in output.

    Returns:
        List[str]: Command parts for the find command.
    """
    from smv import config

    cmd = ["find"]
    valid_search_paths = [p for p in search_paths if os.path.isdir(p)]

    if not valid_search_paths:
        return []

    cmd.extend(valid_search_paths)

    # Use provided excluded patterns or default from config
    if excluded_patterns is None:
        excluded_patterns = config.EXCLUDED_DIRS_FIND_PATTERNS

    # Adjust excluded patterns based on hidden folders setting
    current_excluded_patterns = list(excluded_patterns)
    if config.IGNORE_HIDDEN_FOLDERS and ".*" not in current_excluded_patterns:
        current_excluded_patterns.append(".*")
    elif not config.IGNORE_HIDDEN_FOLDERS and ".*" in current_excluded_patterns:
        current_excluded_patterns.remove(".*")

    # Build prune expressions
    prune_expr = []
    for i, pattern in enumerate(current_excluded_patterns):
        if i > 0:
            prune_expr.append("-o")
        prune_expr.extend(["-name", pattern])

    # Add prune expressions to command
    if prune_expr:
        cmd.extend(["(", *prune_expr, ")", "-prune", "-o"])

    # Add search conditions
    if prune_expr:
        cmd.append("(")
    cmd.extend(["-type", find_type])

    if keyword_conditions:
        cmd.extend(["(", *keyword_conditions, ")"])

    cmd.append("-print0" if print0 else "-print")

    if prune_expr:
        cmd.append(")")

    return cmd
