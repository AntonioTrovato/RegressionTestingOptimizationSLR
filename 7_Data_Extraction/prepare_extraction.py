#!/usr/bin/env python3
"""
Prepare the data-extraction step.

For every row of DataExtraction.xlsx:
  - find the row of the same paper in ../6_Quality_Appraisal/QualityAppraisal.xlsx (match on title + authors)
  - the paper's pdf is ../Analyzed_Studies/<QA row - 1>.pdf   (QA row N+1  <->  N.pdf)
  - if the same paper appears twice in QualityAppraisal.xlsx (duplicate entries), either number works

Outputs:
  - missing_papers.txt   (next to this script): primary studies with no pdf yet, with the file name to use
  - <workdir>/papers.json: one record per unique primary study that HAS a pdf (+ text dump of each pdf
    in <workdir>/texts/<n>.txt), used by the extraction step.

Usage (needs pypdf + cryptography, e.g. the venv in 6_Quality_Appraisal):
    python3 prepare_extraction.py <workdir>
"""

import collections
import json
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_data_extraction_xlsx import norm  # noqa: E402

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("pypdf is required (use the venv in 6_Quality_Appraisal)")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DE_XLSX = HERE / "DataExtraction.xlsx"
QA_XLSX = ROOT / "6_Quality_Appraisal" / "QualityAppraisal.xlsx"
PDF_DIR = ROOT / "Analyzed_Studies"

# pdfs that exist in Analyzed_Studies but cannot be used: they are listed in missing_papers.txt with this note
BAD_PDFS = {342: "the pdf is only a short paywalled preview of the paper, the full text is needed"}  # pdf_number -> reason, for pdfs that exist but must be ignored (wrong paper, preview only...)

URL_RE = re.compile(r"https?://[^\s\)\]>,;]+|(?:github|gitlab|zenodo|figshare|bitbucket)\.[a-z]+/[^\s\)\]>,;]+", re.I)
REF_RE = re.compile(r"\n\s*(references|bibliography)\s*\n", re.I)


_ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304",
            ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306", "H": "\u030b", "k": "\u0328"}
_SPECIAL = {r"\i": "i", r"\j": "j", r"\o": "ø", r"\O": "Ø", r"\ss": "ß", r"\ae": "æ", r"\AE": "Æ",
            r"\aa": "å", r"\AA": "Å", r"\l": "ł", r"\L": "Ł"}


def delatex(s: str) -> str:
    """Turn BibTeX accent commands (\\'{e}, \\c{c}, \\\"o ...) into plain unicode for display."""
    import unicodedata
    s = s or ""
    def acc(m):
        base = m.group(2) or m.group(3)
        base = _SPECIAL.get(base, base) if base.startswith("\\") else base
        return unicodedata.normalize("NFC", base + _ACCENTS[m.group(1)])
    s = re.sub(r"\\([\'`^\"~=.cvuHk])\s*(?:\{\s*(\\?\w+)\s*\}|(\\?\w))", acc, s)
    for k, v in _SPECIAL.items():
        s = re.sub(re.escape(k) + r"(?![a-zA-Z])\s*", v, s)
    return s.replace("{", "").replace("}", "")


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def main():
    workdir = Path(sys.argv[1]).resolve()
    (workdir / "texts").mkdir(parents=True, exist_ok=True)

    qa = openpyxl.load_workbook(QA_XLSX, data_only=True).active
    de = openpyxl.load_workbook(DE_XLSX).active
    have = {int(p.stem) for p in PDF_DIR.glob("*.pdf") if p.stem.isdigit()}

    qa_by_title = collections.defaultdict(list)
    for r in range(2, qa.max_row + 1):
        qa_by_title[norm(qa.cell(r, 1).value)].append(r)

    # group DataExtraction rows describing the same paper
    groups = collections.OrderedDict()
    for r in range(2, de.max_row + 1):
        key = (norm(de.cell(r, 1).value), norm(de.cell(r, 2).value))
        groups.setdefault(key, []).append(r)

    papers, missing, unreadable = [], [], []
    for (t, a), de_rows in groups.items():
        first = de_rows[0]
        title, author = de.cell(first, 1).value, de.cell(first, 2).value
        year, cls = de.cell(first, 3).value, de.cell(first, 4).value
        if cls != "PS":
            continue
        qrows = qa_by_title[t]
        if a:
            qrows = [q for q in qrows if norm(qa.cell(q, 2).value) == a] or qrows
        numbers = [q - 1 for q in qrows]
        got = [n for n in numbers if n in have]
        rec = dict(de_rows=de_rows, title=title, author=author, year=year, qa_numbers=numbers)
        if not got:
            missing.append(rec)
            continue
        n = got[0]
        if n in BAD_PDFS:
            unreadable.append((rec, BAD_PDFS[n]))
            continue
        try:
            text = pdf_text(PDF_DIR / f"{n}.pdf")
        except Exception as exc:  # encrypted/corrupt
            unreadable.append((rec, repr(exc)))
            continue
        if len(text.strip()) < 2000:
            unreadable.append((rec, f"only {len(text.strip())} chars of text (scanned?)"))
            continue
        urls = sorted(set(u.rstrip(".") for u in URL_RE.findall(text)))
        m = REF_RE.search(text, pos=int(len(text) * 0.3))
        body = text[: m.start()] if m else text
        with open(workdir / "texts" / f"{n}.txt", "w", encoding="utf-8", errors="replace") as fh:  # lone surrogates occur in some pdfs
            fh.write(body + "\n\n=== ALL URLS FOUND IN THE PDF (incl. footnotes/references) ===\n" + "\n".join(urls))
        rec.update(pdf_number=n, text_path=str(workdir / "texts" / f"{n}.txt"), chars=len(body))
        papers.append(rec)

    (workdir / "papers.json").write_text(json.dumps(papers, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- missing list for the user -----------------------------------------------------
    lines = [
        "PRIMARY STUDIES WITHOUT A PDF IN Analyzed_Studies/",
        "Save each pdf as <number>.pdf (number in brackets). If two numbers are shown, the paper is",
        "duplicated in QualityAppraisal.xlsx: either one works (use the first).",
        "",
    ]
    todo = [(r, "missing") for r in missing] + [(r, why) for r, why in unreadable]
    for rec, why in sorted(todo, key=lambda x: x[0]["qa_numbers"][0]):
        nums = " / ".join(str(n) for n in rec["qa_numbers"])
        lines.append(f"[{nums}]  ({rec['year']})  {delatex(rec['title'])}")
        lines.append(f"      authors: {delatex(rec['author']) or '(not available)'}")
        if why != "missing":
            lines.append(f"      NOTE: pdf exists but is unreadable: {why}")
    (HERE / "missing_papers.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"unique PS: {len(papers) + len(missing) + len(unreadable)}")
    print(f"  with readable pdf: {len(papers)}")
    print(f"  missing pdf:       {len(missing)}")
    print(f"  unreadable pdf:    {len(unreadable)}")
    for rec, why in unreadable:
        print("   -", rec["qa_numbers"], rec["title"][:70], why)
    chars = sorted(p["chars"] for p in papers)
    print("chars/paper: min", chars[0], "median", chars[len(chars) // 2], "max", chars[-1], "total", sum(chars))


if __name__ == "__main__":
    main()
