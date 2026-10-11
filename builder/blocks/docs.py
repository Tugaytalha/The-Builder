"""A case folder of documents as one text: Markdown and text as they are, Word and Excel converted, other files listed.

Standard library only, so a fresh clone runs it. Nothing here knows a case.
"""
import datetime
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TEXT = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
FIRST = ("readme", "brief")
DATE_FORMATS = set(range(14, 23)) | {45, 46, 47}      # Excel's built-in date and time formats


def docx_text(path):
    """One line per paragraph, in document order (table cells too)."""
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    lines = []
    for p in root.iter(W + "p"):
        parts = [("\t" if el.tag == W + "tab" else el.text or "") for el in p.iter() if el.tag in (W + "t", W + "tab")]
        lines.append("".join(parts))
    return "\n".join(lines).strip()


def _date_styles(z):
    """Indexes of the cell styles that show a number as a date."""
    if "xl/styles.xml" not in z.namelist():
        return set()
    root = ElementTree.fromstring(z.read("xl/styles.xml"))
    custom = {int(f.get("numFmtId")) for f in root.iter(S + "numFmt")
              if re.search(r"[dy]", re.sub(r'"[^"]*"|\[[^]]*\]', "", f.get("formatCode", "").lower()))}
    xfs = root.find(S + "cellXfs")
    return {i for i, xf in enumerate(xfs if xfs is not None else [])
            if int(xf.get("numFmtId", 0)) in DATE_FORMATS | custom}


def xlsx_text(path):
    """Each sheet as a title and tab-separated rows. A number in a date style becomes YYYY-MM-DD."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in si.iter(S + "t"))
                      for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).iter(S + "si")]
        titles = [s.get("name") for s in ElementTree.fromstring(z.read("xl/workbook.xml")).iter(S + "sheet")]
        dates = _date_styles(z)
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[1]).group()))
        out = []
        for i, sheet in enumerate(sheets):
            out.append("### Sheet: " + (titles[i] if i < len(titles) else sheet))
            for row in ElementTree.fromstring(z.read(sheet)).iter(S + "row"):
                cells = []
                for c in row.iter(S + "c"):
                    v = c.find(S + "v")
                    value = "" if v is None else v.text or ""
                    if c.get("t") == "s" and value:
                        value = shared[int(value)]
                    elif c.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in c.iter(S + "t"))
                    elif value and int(c.get("s", 0)) in dates:
                        value = (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(value)))).isoformat()
                    cells.append(value)
                out.append("\t".join(cells))
    return "\n".join(out)


def _order(path, root):
    rel = path.relative_to(root)
    name = path.name.lower()
    first = next((i for i, f in enumerate(FIRST) if name.startswith(f) and len(rel.parts) == 1), len(FIRST))
    return first, str(rel).lower()


def case_text(root):
    """Every file of the folder, README and BRIEF first. A file that is not text gets a line to open it with Read."""
    root = Path(root)
    files = sorted((p for p in root.rglob("*") if p.is_file() and not p.name.startswith((".", "~$"))),
                   key=lambda p: _order(p, root))
    parts = [f"# Case folder: {root.name}"]
    for path in files:
        rel, kind = path.relative_to(root).as_posix(), path.suffix.lower()
        if kind in TEXT:
            body = path.read_text(encoding="utf-8", errors="replace")
        elif kind == ".docx":
            body = docx_text(path)
        elif kind == ".xlsx":
            body = xlsx_text(path)
        else:
            body = f"(Not converted. Open it with the Read tool: case/{rel})"
        parts.append(f"## File: {rel}\n\n{body.strip()}")
    return "\n\n".join(parts) + "\n"
