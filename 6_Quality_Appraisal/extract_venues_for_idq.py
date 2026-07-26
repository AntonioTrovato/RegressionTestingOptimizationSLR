#!/usr/bin/env python3
"""
Extracts the UNIQUE publication venues (journal or booktitle) of papers
that don't yet have an 'idq' field, so you only have to look each venue up
ONCE on SCImago / CORE, instead of once per paper.

Usage:
    python extract_venues_for_idq.py [path_to_6_Quality_Appraisal_folder] [bib_filename]

If no bib filename is given, "QualityAppraisal_WithOldScores.bib" is used
if present, otherwise "QualityAppraisal.bib".

Output:
    venues_to_rank.csv

Columns:
    venue             - the journal/booktitle name as it appears in the bib
    entry_type         - "article" (journal) or other (conference/workshop)
    num_papers         - how many papers use this venue
    scimago_quartile   - for JOURNALS only. One of:
                             q1, q2, q3, q4, not_idx
                         (leave empty for conferences)
    core_rank          - for CONFERENCES/WORKSHOPS only. One of:
                             a_star, a, b, c, d, workshop, not_idx
                         (leave empty for journals)
    notes              - optional free text

Fill in exactly ONE of scimago_quartile / core_rank per row, matching the
venue type (journal -> scimago_quartile, conference/workshop -> core_rank).

Once filled in, use apply_idq.py to compute and write the idq field.
"""

import csv
import os
import re
import sys


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
    """journal/booktitle - falls back to the other field, since some
    exports (e.g. Scopus) put conference venues in 'journal' too."""
    if entry_type == "article":
        return extract_field(entry, "journal") or extract_field(entry, "booktitle")
    return extract_field(entry, "booktitle") or extract_field(entry, "journal")


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
    output_path = os.path.join(folder, "venues_to_rank.csv")

    if not os.path.isfile(bib_path):
        print(f"File not found: {bib_path}")
        sys.exit(1)

    with open(bib_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    print(f"Bib file: {bib_path}")
    print(f"Total entries: {len(entries)}")

    venues = {}  # (venue, entry_type) -> count
    already_have_idq = 0
    no_venue = 0

    for e in entries:
        idq = extract_field(e, "idq")
        if idq is not None and idq != "":
            already_have_idq += 1
            continue

        entry_type = get_entry_type(e)
        venue = get_venue(e, entry_type)
        if not venue:
            no_venue += 1
            continue

        etype = "article" if entry_type == "article" else (entry_type or "unknown")
        key = (venue.strip(), etype)
        venues[key] = venues.get(key, 0) + 1

    rows = sorted(venues.items(), key=lambda kv: (-kv[1], kv[0][0]))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "venue", "entry_type", "num_papers",
            "scimago_quartile", "core_rank", "notes"
        ])
        for (venue, etype), count in rows:
            writer.writerow([venue, etype, count, "", "", ""])

    print(f"\nPapers already with idq (skipped): {already_have_idq}")
    print(f"Papers without a usable venue field (skipped): {no_venue}")
    print(f"Unique venues needing a ranking lookup: {len(rows)}")
    print(f"\nSaved: {output_path}")
    print("\nFor each row: fill in scimago_quartile (q1/q2/q3/q4/not_idx) if "
          "entry_type is 'article', OR core_rank (a_star/a/b/c/d/workshop/not_idx) "
          "otherwise. Then run apply_idq.py.")


if __name__ == "__main__":
    main()