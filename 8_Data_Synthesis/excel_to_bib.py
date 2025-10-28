#!/usr/bin/env python3
import argparse
import glob
import math
import os
import re
import pandas as pd


def first_xlsx_in_cwd():
    files = sorted(glob.glob("*.xlsx")) + sorted(glob.glob("*.xls"))
    return files[0] if files else None


def is_empty(x):
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    return str(x).strip() == ""


def normalize_author_list(raw):
    """Return a BibTeX-friendly author list separated by ' and '."""
    if is_empty(raw):
        return ""
    s = str(raw).strip()
    if " and " in s:
        return re.sub(r"\s+", " ", s)
    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
        return " and ".join(parts)
    comma_tokens = [t.strip() for t in s.split(",")]
    if len(comma_tokens) >= 4 and len(comma_tokens) % 2 == 0:
        pairs = []
        for i in range(0, len(comma_tokens), 2):
            last = comma_tokens[i]
            first = comma_tokens[i + 1]
            if last and first:
                pairs.append(f"{last}, {first}")
        if pairs:
            return " and ".join(pairs)
    if s.count(",") >= 3:
        candidates = re.split(r",(?![^A-Z]*[a-z])", s)
        parts = [p.strip().strip(",") for p in candidates if p.strip().strip(",")]
        if len(parts) > 1:
            return " and ".join(parts)
    return s


def main():
    parser = argparse.ArgumentParser(description="Generate a .bib file from an Excel SLR table (include all papers).")
    parser.add_argument("-i", "--input", help="Excel file (default: first .xlsx in current folder)")
    parser.add_argument("-o", "--output", default="slr.bib", help="Output .bib filename (default: papers_all.bib)")
    args = parser.parse_args()

    in_path = args.input or first_xlsx_in_cwd()
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError("No Excel file found. Put the Excel in this folder or pass it with -i <file.xlsx>.")

    df = pd.read_excel(in_path, header=0)
    if df.shape[1] < 25:
        df = pd.read_excel(in_path, header=None)

    out_lines = []
    for idx, row in df.iterrows():
        try:
            authors_val = row.iloc[2]   # C
            booktitle_val = row.iloc[3] # D
            title_val = row.iloc[4]     # E
            year_val = row.iloc[5]      # F
            journal_val = row.iloc[14]  # O
        except Exception:
            continue

        bib_key = f"paper_{idx + 1}"
        is_conf = not is_empty(booktitle_val)
        entry_type = "inproceedings" if is_conf else "article"

        author_field = normalize_author_list(authors_val)

        def clean(s):
            return "" if is_empty(s) else str(s).strip()

        title = clean(title_val)
        booktitle = clean(booktitle_val)
        journal = clean(journal_val)

        year_str = ""
        if not is_empty(year_val):
            try:
                year_int = int(float(year_val))
                year_str = str(year_int)
            except Exception:
                year_str = str(year_val).strip()

        fields = []
        if author_field:
            fields.append(f"  author = {{{author_field}}}")
        if title:
            fields.append(f"  title  = {{{title}}}")
        if year_str:
            fields.append(f"  year   = {{{year_str}}}")
        if is_conf and booktitle:
            fields.append(f"  booktitle = {{{booktitle}}}")
        if (not is_conf) and journal:
            fields.append(f"  journal   = {{{journal}}}")

        entry = f"@{entry_type}{{{bib_key},\n" + ",\n".join(fields) + "\n}\n"
        out_lines.append(entry)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print(f"Written {len(out_lines)} entries to {args.output}")
    print(f"Source Excel: {in_path}")


if __name__ == "__main__":
    main()
