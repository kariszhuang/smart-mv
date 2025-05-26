"""
Command line interface for the SMV tool.

Usage:
    smv [OPTIONS] FILE_PATH

Examples:
    smv ~/Downloads/document.pdf        # Process and move a PDF file
    smv -v                              # Show version
    smv --help                          # Show help
"""

import os
import sys
import argparse
import traceback

from smv import __version__
from smv.core import SmartMover
from smv.config import check_dependencies


def main():
    """Main entry point for the SMV command line tool."""
    parser = argparse.ArgumentParser(
        description="Smart Move (smv) - AI-powered file organization tool",
        epilog="""
Examples:
  smv ~/Downloads/document.pdf        # Process and move a PDF file
  smv --dry-run ~/Desktop/image.jpg   # Analyze without moving
        """,
    )

    # Add version argument
    parser.add_argument(
        "-v", "--version", action="version", version=f"SMV v{__version__}"
    )

    # Add file path argument
    parser.add_argument("file_path", help="Path to the file to organize")

    # Parse arguments
    args = parser.parse_args()
    file_path_arg = args.file_path

    print(f"Smart Move v{__version__} starting for: {file_path_arg}")

    # Check dependencies
    check_dependencies()

    # Validate file path
    if not os.path.exists(file_path_arg):
        print(f"Error: File '{file_path_arg}' does not exist.")
        sys.exit(1)
    elif not os.path.isfile(file_path_arg):
        print(f"Error: Path '{file_path_arg}' is not a file.")
        sys.exit(1)

    try:
        # Create SmartMover instance and sort file
        mover = SmartMover(file_path_arg)
        mover.sort_file()
    except Exception as e:
        print(f"Critical error in execution: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n--- End of Script ---")


if __name__ == "__main__":
    main()
