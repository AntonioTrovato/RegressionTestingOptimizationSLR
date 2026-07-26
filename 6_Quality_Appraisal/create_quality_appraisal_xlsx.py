#!/usr/bin/env python3
"""
Creates QualityAppraisal.xlsx from QualityAppraisal_WithIDQ.bib, one row
per paper.

Requires: openpyxl (not in the standard library)
    pip install openpyxl

Usage:
    python create_quality_appraisal_xlsx.py [path_to_6_Quality_Appraisal_folder]

If no argument is given, the current directory is used
(assumed to be 6_Quality_Appraisal).

Expected input:
    6_Quality_Appraisal/QualityAppraisal_WithIDQ.bib

Output:
    6_Quality_Appraisal/QualityAppraisal.xlsx

Columns:
    title, author, idq,
    cdq_1_a, cdq_1_b, cdq_2_a, cdq_2_b, cdq_3_a, cdq_3_b,
    cdq_4_a, cdq_4_b, cdq_5_a, cdq_5_b, cdq_6_a, cdq_6_b,
    cdq_a, cdq_b, cdq, fdq

All papers already have idq, so that column is always filled.
Primary studies (PS) only use cdq_1..cdq_4 -> cdq_5_a/b and cdq_6_a/b are
left empty for them (as in the bib itself).
Papers not yet analyzed (no cdq/fdq fields at all in the bib) are left
with all cdq/fdq columns empty in the spreadsheet.
"""

import os
import re
import sys

try:
    import openpyxl
except ImportError:
    print("This script requires the 'openpyxl' package.")
    print("Install it with:  pip install openpyxl")
    sys.exit(1)


COLUMNS = (
    ["title", "author", "idq"]
    + [f"cdq_{i}_{letter}" for i in range(1, 7) for letter in ("a", "b")]
    + ["cdq_a", "cdq_b", "cdq", "fdq"]
)


# --------------------------------------------------------------------------
# BibTeX parsing helpers
# --------------------------------------------------------------------------

def split_entries(text):
    starts = [m.start() for m in re.finditer(r'@\w+\s*\{', text)]
    entries = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        entry = text[start:end].strip()
        if entry:
            entries.append(entry)
    return entries


def extract_field(entry, field):
    pattern = re.compile(r'\b' + re.escape(field) + r'\s*=\s*(\{|")', re.IGNORECASE)
    m = pattern.search(entry)
    if not m:
        return None
    open_char = m.group(1)
    start = m.end()
    if open_char == '"':
        end = entry.find('"', start)
        return entry[start:end].strip() if end != -1 else None
    depth = 1
    i = start
    while i < len(entry) and depth > 0:
        if entry[i] == '{':
            depth += 1
        elif entry[i] == '}':
            depth -= 1
        i += 1
    return entry[start:i - 1].strip()


def to_number_if_possible(value):
    """Convert a numeric-looking string to float/int, so Excel treats it
    as a number rather than text."""
    if value is None or value == "":
        return None
    try:
        f = float(value)
        if f.is_integer():
            return int(f)
        return f
    except (TypeError, ValueError):
        return value


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    folder = os.path.abspath(folder)

    bib_path = os.path.join(folder, "QualityAppraisal_WithIDQ.bib")
    output_path = os.path.join(folder, "QualityAppraisal.xlsx")

    if not os.path.isfile(bib_path):
        print(f"File not found: {bib_path}")
        sys.exit(1)

    with open(bib_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    print(f"Bib file: {bib_path}")
    print(f"Papers found: {len(entries)}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(COLUMNS)

    for e in entries:
        row = []
        for col in COLUMNS:
            value = extract_field(e, col)
            if col in ("title", "author"):
                row.append(value if value is not None else "")
            else:
                row.append(to_number_if_possible(value))
        ws.append(row)

    wb.save(output_path)

    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()