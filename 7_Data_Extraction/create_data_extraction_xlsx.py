#!/usr/bin/env python3
"""
Build DataExtraction.xlsx from PostQualityAppraisal.xlsx.

Steps:
  1. Delete every row (entirely) whose FDQ (column S) is < 0.5.
  2. For the surviving rows (FDQ >= 0.5), clear all columns except A (title) and B (author).
  3. Make column C the publication-year column (header "year") and column D the classification
     column (header "classification": PS / SLR / RW), filled by matching each row's title (A)
     and authors (B) against ../6_Quality_Appraisal/QualityAppraisal.bib.
  4. Delete every row (entirely) whose year is <= 2012 (rows with an unknown year are kept).
  5. Delete duplicate rows (same title appearing more than once, even if the author strings are
     formatted differently): the first is kept.
  6. Remove every formula and every cell fill colour from the sheet.
  7. Delete papers marked NON ACCESSIBLE in 6_Quality_Appraisal/papers_to_delete.txt.
  8. Save the result as DataExtraction.xlsx (same folder as this script).

Run from 7_Data_Extraction/:

    python3 create_data_extraction_xlsx.py

Notes:
  - FDQ is read from the values cached in the xlsx (Excel stores the computed result of
    =AVERAGE(...) formulas when saving). If a row has no cached FDQ the script stops, so open
    and re-save PostQualityAppraisal.xlsx in Excel first.
  - Rows with no authors in column B (snowballed papers) are matched on title only.
  - Anything that could not be matched unambiguously is listed at the end and the affected
    cell(s) are left empty, so you can fill them in by hand.
"""

import collections
import difflib
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl
from copy import copy
from openpyxl.styles import PatternFill

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_XLSX = SCRIPT_DIR / "PostQualityAppraisal.xlsx"
BIB_PATH = SCRIPT_DIR.parent / "6_Quality_Appraisal" / "QualityAppraisal.bib"
OUTPUT_XLSX = SCRIPT_DIR / "DataExtraction.xlsx"
DUPLICATES_TXT = SCRIPT_DIR / "removed_duplicates.txt"
PAPERS_TO_DELETE_TXT = SCRIPT_DIR.parent / "6_Quality_Appraisal" / "papers_to_delete.txt"

COL_TITLE, COL_AUTHOR, COL_YEAR, COL_CLASS, COL_FDQ = 1, 2, 3, 4, 19  # A, B, C, D, S
FDQ_THRESHOLD = 0.5
MAX_OLD_YEAR = 2012  # papers from this year (included) and earlier are removed
EPS = 1e-9  # guard against float noise such as 0.49999999999


# --------------------------------------------------------------------------
# BibTeX parsing
# --------------------------------------------------------------------------

def parse_bib(path: Path) -> list[dict]:
    """Minimal BibTeX parser: returns one {field: value} dict per entry (lower-case field names)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    entries = []
    for chunk in re.split(r"\n(?=@)", text):
        if not chunk.lstrip().startswith("@"):
            continue
        fields = {}
        for m in re.finditer(r"^\s*(\w+)\s*=\s*", chunk, re.M):
            name, i = m.group(1).lower(), m.end()
            if i < len(chunk) and chunk[i] == "{":
                depth, j = 0, i
                while j < len(chunk):
                    if chunk[j] == "{":
                        depth += 1
                    elif chunk[j] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                fields.setdefault(name, chunk[i + 1:j])
            else:
                mm = re.match(r'"([^"]*)"|([^,\n]*)', chunk[i:])
                fields.setdefault(name, (mm.group(1) or mm.group(2) or "").strip())
        entries.append(fields)
    return entries


def norm(s) -> str:
    """Normalise titles/authors for comparison: strip LaTeX accents, accents, case, punctuation."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = re.sub(r"\\[\"'`^~=.]\s*\{?(\w)\}?", r"\1", s)   # \"{o}  \'e  \~{a}
    s = re.sub(r"\\[cvuHkr]\s*\{?(\w)\}?", r"\1", s)     # \c{c}  \v{s}
    s = re.sub(r"\\[a-zA-Z]+", "", s)                    # any remaining LaTeX command
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def extract_year(raw) -> int | None:
    m = re.search(r"\d{4}", str(raw or ""))
    return int(m.group(0)) if m else None


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

class BibLookup:
    def __init__(self, entries: list[dict]):
        self.by_title = collections.defaultdict(list)
        for e in entries:
            self.by_title[norm(e.get("title"))].append(e)

    @staticmethod
    def _resolve(candidates: list[dict], author: str):
        """Return ({'year':..., 'classification':...}, notes). A value is None if the candidate
        entries don't agree on it (or it's missing)."""
        if len(candidates) > 1 and author:
            narrowed = [c for c in candidates if norm(c.get("author")) == author]
            if narrowed:
                candidates = narrowed
        notes = []
        years = {extract_year(c.get("year")) for c in candidates} - {None}
        classes = {(c.get("classification") or "").strip().upper() for c in candidates} - {""}
        out = {}
        for name, values in (("year", years), ("classification", classes)):
            if len(values) == 1:
                out[name] = next(iter(values))
            else:
                out[name] = None
                notes.append(f"{name}: " + ("missing in bib" if not values else f"ambiguous {sorted(values)}"))
        return out, notes

    def find(self, title, author):
        """Return (info, how, notes) where how is 'exact' | 'fuzzy' | None."""
        t, a = norm(title), norm(author)

        cands = self.by_title.get(t)
        if cands:
            info, notes = self._resolve(cands, a)
            return info, "exact", notes

        # Fallback: titles that differ slightly (e.g. a "12.4 - " prefix, a trailing period).
        best_key, best_score = None, 0.0
        for key in self.by_title:
            if not key:
                continue
            short, long_ = sorted((t, key), key=len)
            if short and short in long_ and len(short) / len(long_) >= 0.8:
                score = 0.99
            else:
                score = difflib.SequenceMatcher(None, t, key).ratio()
            if score > best_score:
                best_key, best_score = key, score
        if best_key is not None and best_score >= 0.9:
            info, notes = self._resolve(self.by_title[best_key], a)
            return info, "fuzzy", [f"fuzzy title match ({best_score:.2f}) -> '{best_key[:70]}'"] + notes

        return {"year": None, "classification": None}, None, ["no matching title in bib"]


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    for p in (INPUT_XLSX, BIB_PATH):
        if not p.is_file():
            print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)

    wb = openpyxl.load_workbook(INPUT_XLSX, data_only=True)  # data_only: use cached values, no formulas
    ws = wb.active

    # ---- 1. delete rows with FDQ < 0.5 -------------------------------------------------
    to_delete = []
    for r in range(2, ws.max_row + 1):
        fdq = ws.cell(row=r, column=COL_FDQ).value
        if not isinstance(fdq, (int, float)):
            if ws.cell(row=r, column=COL_TITLE).value is None:
                continue  # fully empty row
            print(f"Row {r} has no numeric FDQ in column S ({fdq!r}). "
                  f"Open {INPUT_XLSX.name} in Excel and save it so the formulas get computed.", file=sys.stderr)
            sys.exit(1)
        if fdq < FDQ_THRESHOLD - EPS:
            to_delete.append(r)

    for r in reversed(to_delete):  # bottom-up so indices stay valid
        ws.delete_rows(r)
    print(f"Deleted {len(to_delete)} rows with FDQ < {FDQ_THRESHOLD}; {ws.max_row - 1} rows remain.")

    # ---- 2. clean every column except A and B (values AND formatting) ------------------
    header_style = copy(ws.cell(row=1, column=COL_TITLE)._style)
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=COL_YEAR, max_col=ws.max_column):
        for cell in row:
            cell.value = None
            cell.style = "Normal"

    # ---- 3. look up year + classification in the bib -----------------------------------
    entries = parse_bib(BIB_PATH)
    lookup = BibLookup(entries)
    print(f"Parsed {len(entries)} bib entries from {BIB_PATH.name}.")

    results = []  # one (info, how, notes) per data row, in row order
    for r in range(2, ws.max_row + 1):
        results.append(lookup.find(ws.cell(row=r, column=COL_TITLE).value,
                                   ws.cell(row=r, column=COL_AUTHOR).value))

    # ---- 4. delete rows with year <= 2012 ----------------------------------------------
    first_data_row = 2
    old_rows = [r for r, (info, _, _) in zip(range(first_data_row, ws.max_row + 1), results)
                if info["year"] is not None and info["year"] <= MAX_OLD_YEAR]
    for r in reversed(old_rows):
        ws.delete_rows(r)
    old_set = set(old_rows)
    results = [res for r, res in zip(range(first_data_row, first_data_row + len(results)), results)
               if r not in old_set]
    print(f"Deleted {len(old_rows)} rows with year <= {MAX_OLD_YEAR}; {ws.max_row - 1} rows remain.")

    # ---- 4b. delete duplicate rows (same title), keeping the first -----------
    seen, dup_rows, dup_report = {}, [], []
    for r in range(first_data_row, ws.max_row + 1):
        key = norm(ws.cell(row=r, column=COL_TITLE).value)  # title only: author formats differ between bib entries
        if key in seen:
            dup_rows.append(r)
            kept = seen[key]
            dup_report.append((ws.cell(row=r, column=COL_TITLE).value,
                               ws.cell(row=r, column=COL_AUTHOR).value,
                               ws.cell(row=kept, column=COL_AUTHOR).value))
        else:
            seen[key] = r
    for r in reversed(dup_rows):
        ws.delete_rows(r)
    DUPLICATES_TXT.write_text(
        "DUPLICATE PAPERS REMOVED FROM DataExtraction.xlsx (same title appearing more than once; "
        "the first copy was kept)\n\n"
        + "\n".join(f"{i}. {t}\n     removed copy authors: {a or '(none)'}\n     kept copy authors:    {k or '(none)'}\n"
                    for i, (t, a, k) in enumerate(dup_report, 1)),
        encoding="utf-8")
    dup_set = set(dup_rows)
    results = [res for r, res in zip(range(first_data_row, first_data_row + len(results)), results)
               if r not in dup_set]
    last_row = ws.max_row
    print(f"Deleted {len(dup_rows)} duplicate rows (same title); {last_row - 1} rows remain.")

    # ---- 4c. delete papers marked "NON ACCESSIBLE" in 6_Quality_Appraisal/papers_to_delete.txt ----
    non_accessible = set()
    if PAPERS_TO_DELETE_TXT.is_file():
        for line in PAPERS_TO_DELETE_TXT.read_text(encoding="utf-8").splitlines():
            if "NON ACCESSIBLE" in line.upper():
                non_accessible.add(norm(line.split("->")[0]))
    na_rows = [r for r in range(first_data_row, ws.max_row + 1)
               if norm(ws.cell(row=r, column=COL_TITLE).value) in non_accessible]
    for r in reversed(na_rows):
        ws.delete_rows(r)
    na_set = set(na_rows)
    results = [res for r, res in zip(range(first_data_row, first_data_row + len(results)), results)
               if r not in na_set]
    last_row = ws.max_row
    print(f"Deleted {len(na_rows)} NON ACCESSIBLE papers; {last_row - 1} rows remain.")

    # ---- 5. write columns C (year) and D (classification) -------------------------------
    for col, name in ((COL_YEAR, "year"), (COL_CLASS, "classification")):
        hdr = ws.cell(row=1, column=col)
        hdr.value = name
        hdr._style = copy(header_style)

    fuzzy, problems = [], []
    for r, (info, how, notes) in zip(range(2, last_row + 1), results):
        title = ws.cell(row=r, column=COL_TITLE).value
        if info["year"] is not None:
            ws.cell(row=r, column=COL_YEAR).value = info["year"]
        if info["classification"] is not None:
            ws.cell(row=r, column=COL_CLASS).value = info["classification"]
        if how == "fuzzy" and info["year"] is not None and info["classification"] is not None:
            fuzzy.append((r, title, info, notes))
        elif info["year"] is None or info["classification"] is None:
            problems.append((r, title, notes))

    # drop the now-empty columns after D
    if ws.max_column > COL_CLASS:
        ws.delete_cols(COL_CLASS + 1, ws.max_column - COL_CLASS)
    for letter in list(ws.column_dimensions):
        if openpyxl.utils.column_index_from_string(letter) > COL_CLASS:
            del ws.column_dimensions[letter]

    # ---- 6. no formulas, no coloured cells ---------------------------------------------
    no_fill = PatternFill(fill_type=None)
    n_formulas = 0
    for row in ws.iter_rows(min_row=1, max_row=last_row, min_col=1, max_col=COL_CLASS):
        for cell in row:
            cell.fill = no_fill
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.value = None
                n_formulas += 1
    ws.conditional_formatting = type(ws.conditional_formatting)()  # drop any colour rules
    ws.auto_filter.ref = f"A1:D{last_row}"

    wb.save(OUTPUT_XLSX)

    # ---- report ------------------------------------------------------------------------
    print(f"Year + classification filled for {last_row - 1 - len(problems)}/{last_row - 1} rows.")
    if n_formulas:
        print(f"Removed {n_formulas} leftover formulas.")
    if fuzzy:
        print("\nMatched by approximate title (please eyeball):")
        for r, title, info, notes in fuzzy:
            print(f"  row {r}: {title}\n          year={info['year']} class={info['classification']}  {'; '.join(notes)}")
    if problems:
        print("\nSomething NOT filled (fill manually):", file=sys.stderr)
        for r, title, notes in problems:
            print(f"  row {r}: {title}  [{'; '.join(notes)}]", file=sys.stderr)
    print(f"\nSaved {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
