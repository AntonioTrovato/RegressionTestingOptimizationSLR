#!/usr/bin/env python3
"""
Write the extracted data (extraction_results.json) into DataExtraction.xlsx and build the document
of new taxonomy classes (NewTaxonomyClasses.docx).

New columns (E..L): optimization class | taxonomy class | algorithm family | objectives |
                    reproducibility | sut | leveraged feature | evaluation metric

Taxonomy cell convention: an existing class is written as just its name. A class that is NEW
(not in the Yoo & Harman taxonomy) is written as "Name: description" in the first row (top to bottom)
where it appears, and as just "Name" in the following rows (from then on it is a known class).

Rows without an extraction result (SLR/RW rows, or papers whose pdf is still missing) are left empty.
The script is idempotent: re-run it whenever extraction_results.json grows.

Run from 7_Data_Extraction/ (needs openpyxl + python-docx, e.g. the venv in 6_Quality_Appraisal):

    ../6_Quality_Appraisal/.venv/bin/python3 apply_extraction.py

Note: create_data_extraction_xlsx.py regenerates DataExtraction.xlsx from scratch (wiping these
columns); re-run this script afterwards.
"""

import json
import sys
from copy import copy
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_data_extraction_xlsx import norm  # noqa: E402

HERE = Path(__file__).resolve().parent
XLSX = HERE / "DataExtraction.xlsx"
RESULTS = HERE / "extraction_results.json"
NEW_TAX_DOCX = HERE / "NewTaxonomyClasses.docx"

COLUMNS = [  # (header, json key, width)
    ("optimization class", "optimization_class", 18),
    ("taxonomy class", "taxonomy_class", 45),
    ("algorithm family", "algorithm_family", 32),
    ("objectives", "objectives", 38),
    ("reproducibility", "reproducibility", 16),
    ("sut", "sut", 60),
    ("leveraged feature", "leveraged feature", 40),
    ("evaluation metric", "evaluation metric", 34),
]
FIRST_COL = 5  # E
CLASS_ORDER = ["prioritization", "selection", "minimization"]


def taxonomy_cell(names, descriptions, introduced):
    parts = []
    for name in names:
        desc = descriptions.get(name)
        if desc and name not in introduced:
            introduced.add(name)
            parts.append(f"{name}: {desc}")
        else:
            parts.append(name)
    return " + ".join(parts)


def main():
    records = json.loads(RESULTS.read_text(encoding="utf-8"))
    by_key = {norm(r["title"]): r for r in records}  # titles are unique after de-duplication

    # canonical description per new class = first non-empty one found in the results
    descriptions = {}
    for r in records:
        for name, desc in (r.get("new_class_descriptions") or {}).items():
            if desc:
                descriptions.setdefault(name, desc)

    wb = openpyxl.load_workbook(XLSX)
    ws = wb.active
    header_style = copy(ws.cell(row=1, column=1)._style)
    for i, (header, _, width) in enumerate(COLUMNS):
        c = ws.cell(row=1, column=FIRST_COL + i)
        c.value = header
        c._style = copy(header_style)
        ws.column_dimensions[openpyxl.utils.get_column_letter(FIRST_COL + i)].width = width

    introduced = set()
    new_class_usage = {}  # name -> {"opt": set(), "n": int}
    filled = 0
    for r in range(2, ws.max_row + 1):
        rec = by_key.get(norm(ws.cell(row=r, column=1).value))
        for i in range(len(COLUMNS)):  # reset, so re-runs never leave stale values
            ws.cell(row=r, column=FIRST_COL + i).value = None
        if rec is None:
            continue
        filled += 1
        for i, (_, key, _) in enumerate(COLUMNS):
            if key == "taxonomy_class":
                names = rec[key] if isinstance(rec[key], list) else [rec[key]]
                value = taxonomy_cell(names, descriptions, introduced)
                for n in names:
                    if n in descriptions:
                        u = new_class_usage.setdefault(n, {"opt": set(), "n": 0})
                        u["n"] += 1
                        u["opt"].update(o.strip() for o in str(rec["optimization_class"]).split("+"))
            else:
                value = rec.get(key)
            cell = ws.cell(row=r, column=FIRST_COL + i)
            cell.value = value
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(FIRST_COL + len(COLUMNS) - 1)}{ws.max_row}"
    wb.save(XLSX)
    print(f"Filled {filled} rows in {XLSX.name}")

    write_new_taxonomy_doc(descriptions, new_class_usage)


def write_new_taxonomy_doc(descriptions, usage):
    from docx import Document

    doc = Document()
    doc.add_heading("New taxonomy classes", level=0)
    doc.add_paragraph(
        "Taxonomy classes that emerged during data extraction because no class of the Yoo & Harman taxonomy "
        "described the proposed method, grouped by optimization class."
    )
    for opt in CLASS_ORDER:
        doc.add_heading(f"{opt.capitalize()} taxonomy - new classes", level=1)
        names = sorted((n for n, u in usage.items() if opt in u["opt"]), key=lambda n: (-usage[n]["n"], n))
        if not names:
            doc.add_paragraph("(none)")
        for n in names:
            p = doc.add_paragraph()
            p.add_run(f"{n}: ").bold = True
            p.add_run(f"{descriptions[n]} ")
            p.add_run(f"[{usage[n]['n']} paper{'s' if usage[n]['n'] != 1 else ''}]").italic = True
    doc.save(NEW_TAX_DOCX)
    print(f"Wrote {NEW_TAX_DOCX.name} ({len(usage)} new classes)")


if __name__ == "__main__":
    main()
