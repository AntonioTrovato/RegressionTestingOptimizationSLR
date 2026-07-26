#!/usr/bin/env python3
"""
Applies the IDQ score to every paper that doesn't already have one, based
on the venue rankings you filled in venues_to_rank.csv (see
extract_venues_for_idq.py).

Usage:
    python apply_idq.py [path_to_6_Quality_Appraisal_folder] [bib_filename]

If no bib filename is given, "QualityAppraisal_WithOldScores.bib" is used
if present, otherwise "QualityAppraisal.bib".

Expected input:
    <bib_filename>
    venues_to_rank.csv   (filled in)

Output:
    QualityAppraisal_WithIDQ.bib
    papers_without_venue.txt   - titles of papers that have no journal/
                                  booktitle field at all (so idq could not
                                  be computed), for you to handle manually

--------------------------------------------------------------------------
IDQ TABLE
--------------------------------------------------------------------------
    scimago_quartile (journals only):
        q1      -> 1.0
        q2      -> 0.8
        q3      -> 0.5
        q4      -> 0.2
        not_idx -> 0.4

    core_rank (conferences/workshops only):
        a_star, a -> 1.0
        b         -> 0.8
        c         -> 0.5
        d         -> 0.2
        workshop  -> 0.4
        not_idx   -> 0.4

If a venue row in the CSV is left completely empty (no scimago_quartile,
no core_rank filled) -> idq = 0.4 (Not indexed / Workshop), matching the
original table's default.

Papers that already have a non-empty 'idq' field are left untouched, so
this script is safe to run again, and produces identical idq values on
papers shared with the old corpus regardless of which bib file you run it
on (as requested, for reproducibility by reviewers who don't have access
to the old SLR data).
--------------------------------------------------------------------------
"""

import csv
import os
import re
import sys


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


def get_entry_type(entry):
    m = re.match(r'@(\w+)\s*\{', entry)
    return m.group(1).lower() if m else None


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


def get_venue(entry, entry_type):
    if entry_type == "article":
        return extract_field(entry, "journal") or extract_field(entry, "booktitle")
    return extract_field(entry, "booktitle") or extract_field(entry, "journal")


def add_field(entry, name, value):
    entry = entry.rstrip()
    if not entry.endswith("}"):
        return entry + f",\n{name} = {{{value}}}\n}}"
    body = entry[:-1].rstrip()
    if body.endswith(","):
        body = body[:-1]
    return body + f",\n{name} = {{{value}}}\n}}"


# --------------------------------------------------------------------------
# IDQ computation
# --------------------------------------------------------------------------

SCIMAGO_MAP = {"q1": 1.0, "q2": 0.8, "q3": 0.5, "q4": 0.2, "not_idx": 0.4}
CORE_MAP = {
    "a_star": 1.0, "a": 1.0,
    "b": 0.8,
    "c": 0.5,
    "d": 0.2,
    "workshop": 0.4,
    "not_idx": 0.4,
}


def compute_idq(row):
    """Priority: scimago_quartile > core_rank.
    If neither is filled in -> 0.4 (Not indexed / Workshop)."""
    scimago = (row.get("scimago_quartile") or "").strip().lower()
    if scimago:
        if scimago not in SCIMAGO_MAP:
            print(f"  WARNING: unrecognized scimago_quartile '{scimago}' "
                  f"for venue '{row.get('venue')}' - ignoring it")
        else:
            return SCIMAGO_MAP[scimago]

    core = (row.get("core_rank") or "").strip().lower()
    if core:
        if core not in CORE_MAP:
            print(f"  WARNING: unrecognized core_rank '{core}' "
                  f"for venue '{row.get('venue')}' - ignoring it")
        else:
            return CORE_MAP[core]

    return 0.4  # nothing filled in -> Not indexed / Workshop


def load_venue_ranking(csv_path):
    """Returns dict (venue, entry_type) -> idq"""
    mapping = {}
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            venue = (row.get("venue") or "").strip()
            etype = (row.get("entry_type") or "").strip()
            if not venue:
                continue
            mapping[(venue, etype)] = compute_idq(row)
    return mapping


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    folder = os.path.abspath(folder)

    if len(sys.argv) > 2:
        bib_filename = sys.argv[2]
    elif os.path.isfile(os.path.join(folder, "QualityAppraisal_WithOldScores.bib")):
        bib_filename = "QualityAppraisal_WithOldScores.bib"
    else:
        bib_filename = "QualityAppraisal.bib"

    bib_path = os.path.join(folder, bib_filename)
    csv_path = os.path.join(folder, "venues_to_rank.csv")
    output_path = os.path.join(folder, "QualityAppraisal_WithIDQ.bib")
    missing_venue_txt_path = os.path.join(folder, "papers_without_venue.txt")

    if not os.path.isfile(bib_path):
        print(f"File not found: {bib_path}")
        sys.exit(1)
    if not os.path.isfile(csv_path):
        print(f"File not found: {csv_path}")
        print("Run extract_venues_for_idq.py first, fill in the CSV, then run this script.")
        sys.exit(1)

    print(f"Bib file: {bib_path}")
    print(f"CSV file: {csv_path}")
    print(f"Output:   {output_path}\n")

    venue_ranking = load_venue_ranking(csv_path)

    with open(bib_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    already_had_idq = 0
    newly_assigned = 0
    venue_not_in_csv = 0
    result_entries = []
    missing_venue_titles = []

    idq_distribution = {}

    for e in entries:
        existing_idq = extract_field(e, "idq")
        if existing_idq is not None and existing_idq != "":
            already_had_idq += 1
            result_entries.append(e)
            continue

        entry_type = get_entry_type(e)
        etype = "article" if entry_type == "article" else (entry_type or "unknown")
        venue = get_venue(e, entry_type)

        if not venue:
            title = extract_field(e, "title") or "(no title found)"
            missing_venue_titles.append(title)
            result_entries.append(e)
            continue

        key = (venue.strip(), etype)
        if key not in venue_ranking:
            venue_not_in_csv += 1
            result_entries.append(e)
            continue

        idq = venue_ranking[key]
        result_entries.append(add_field(e, "idq", idq))
        newly_assigned += 1
        idq_distribution[idq] = idq_distribution.get(idq, 0) + 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(result_entries))
        if result_entries:
            f.write("\n")

    with open(missing_venue_txt_path, "w", encoding="utf-8") as f:
        for title in missing_venue_titles:
            f.write(title + "\n")

    print("=== RESULTS ===")
    print(f"Already had idq (untouched): {already_had_idq}")
    print(f"Newly assigned idq: {newly_assigned}")
    for idq, count in sorted(idq_distribution.items()):
        print(f"    idq = {idq}: {count} papers")
    print(f"Skipped - no venue field found: {len(missing_venue_titles)} "
          f"(titles written to {missing_venue_txt_path})")
    print(f"Skipped - venue not found in venues_to_rank.csv: {venue_not_in_csv}")
    print(f"\nSaved: {output_path}")

    if venue_not_in_csv:
        print("\nSome venues are missing from the CSV (probably new papers added "
              "after you generated venues_to_rank.csv). Re-run "
              "extract_venues_for_idq.py to get an updated list of venues "
              "still needing a ranking.")


if __name__ == "__main__":
    main()