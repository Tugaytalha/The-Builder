import zipfile

from builder.blocks.docs import case_text

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _docx(path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document {W}><w:body>{body}</w:body></w:document>")


def _xlsx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {S}><sheets><sheet name="Müşteriler" sheetId="1"/></sheets></workbook>')
        z.writestr("xl/sharedStrings.xml", f"<sst {S}><si><t>Ad</t></si><si><t>Doğum</t></si><si><t>Ayşe</t></si></sst>")
        z.writestr("xl/styles.xml", f'<styleSheet {S}><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {S}><sheetData>'
                   '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                   '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" s="1"><v>32216</v></c><c r="C2"><v>1250.5</v></c></row>'
                   '</sheetData></worksheet>')


def test_case_text_puts_readme_and_brief_first_and_converts_word_and_excel(tmp_path):
    (tmp_path / "BRIEF.md").write_text("Brief text")
    (tmp_path / "README.md").write_text("Readme text")
    (tmp_path / "a-analysis.md").write_text("Analysis text")
    sub = tmp_path / "ekler"
    sub.mkdir()
    _docx(sub / "sozlesme.docx", ["Birinci madde", "İkinci madde"])
    _xlsx(sub / "musteriler.xlsx")
    (sub / "akis.pdf").write_bytes(b"%PDF-1.4")
    text = case_text(tmp_path)
    assert text.index("Readme text") < text.index("Brief text") < text.index("Analysis text")
    assert "Birinci madde\nİkinci madde" in text
    assert "Müşteriler" in text and "Ad\tDoğum" in text and "Ayşe\t1988-03-14\t1250.5" in text
    assert "## File: ekler/akis.pdf" in text and "Read" in text
