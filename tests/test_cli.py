import unittest

from smv import cli


class CliTest(unittest.TestCase):
    def test_normalize_argv_preserves_subcommands(self):
        self.assertEqual(cli._normalize_argv(["ai", "show"]), ["ai", "show"])

    def test_normalize_argv_wraps_file_path_with_sort(self):
        self.assertEqual(cli._normalize_argv(["/tmp/file.pdf"]), ["sort", "/tmp/file.pdf"])

    def test_normalize_argv_preserves_flags(self):
        self.assertEqual(cli._normalize_argv(["--version"]), ["--version"])


if __name__ == "__main__":
    unittest.main()
