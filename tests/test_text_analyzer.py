import os
import tempfile
import unittest
import zipfile

from smv.analyzers.text_analyzer import TextAnalyzer


class TextAnalyzerDocxTest(unittest.TestCase):
    def _write_docx(self, file_path: str, document_xml: str) -> None:
        with zipfile.ZipFile(file_path, "w") as docx_zip:
            docx_zip.writestr("word/document.xml", document_xml)

    def test_extract_from_docx_reads_text(self):
        document_xml = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:r><w:t>Hello</w:t></w:r><w:r><w:t> world</w:t></w:r></w:p>
            <w:p><w:r><w:t>Second line</w:t></w:r></w:p>
          </w:body>
        </w:document>
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = os.path.join(tmp_dir, "sample.docx")
            self._write_docx(docx_path, document_xml)

            success, extracted_text = TextAnalyzer.extract_from_docx(docx_path)

            self.assertTrue(success)
            self.assertIn("Hello world", extracted_text)
            self.assertIn("Second line", extracted_text)

    def test_extract_from_docx_requires_main_document_xml(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = os.path.join(tmp_dir, "missing-main.docx")
            with zipfile.ZipFile(docx_path, "w") as docx_zip:
                docx_zip.writestr("[Content_Types].xml", "<Types></Types>")

            success, error_text = TextAnalyzer.extract_from_docx(docx_path)

            self.assertFalse(success)
            self.assertIn("document.xml", error_text)


if __name__ == "__main__":
    unittest.main()
