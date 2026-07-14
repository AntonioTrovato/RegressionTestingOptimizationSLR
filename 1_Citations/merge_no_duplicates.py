#!/usr/bin/env python3
"""
Merges the current .bib files from ACM, IEEE, ScienceDirect and Scopus
into a single deduplicated file: ../2_Duplicate_Removal/CitationsNoDuplicates.bib

Usage:
    python merge_no_duplicates.py [path_to_1_Citations_folder]

If no argument is given, the current directory is used (assumed to be 1_Citations).

Expected structure:
    1_Citations/ACM/ACM.bib
    1_Citations/IEEE/IEEE.bib
    1_Citations/ScienceDirect/ScienceDirect.bib
    1_Citations/Scopus/Scopus.bib

Output:
    2_Duplicate_Removal/CitationsNoDuplicates.bib   (sibling of 1_Citations)

Deduplication is based on DOI when available, falling back to a normalized
title otherwise. The first occurrence found (in DATABASES order) is kept.
"""

import os
import re
import sys

DATABASES = ["ACM", "IEEE", "ScienceDirect", "Scopus"]


def split_entries(text):
    """Split the content of a .bib file into a list of entries (strings),
    each starting at '@' up to the next entry."""
    starts = [m.start() for m in re.finditer(r'@\w+\s*\{', text)]
    entries = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        entry = text[start:end].strip()
        if entry:
            entries.append(entry)
    return entries


def extract_field(entry, field):
    """Extract the value of a field (e.g. doi, title) from a BibTeX entry.
    Handles values delimited by {} or by "" ."""
    pattern = re.compile(
        r'\b' + re.escape(field) + r'\s*=\s*(\{|")',
        re.IGNORECASE,
    )
    m = pattern.search(entry)
    if not m:
        return None

    open_char = m.group(1)
    start = m.end()

    if open_char == '"':
        end = entry.find('"', start)
        if end == -1:
            return None
        return entry[start:end].strip()

    # open_char == '{': handle nested braces
    depth = 1
    i = start
    while i < len(entry) and depth > 0:
        if entry[i] == '{':
            depth += 1
        elif entry[i] == '}':
            depth -= 1
        i += 1
    return entry[start:i - 1].strip()


def normalize_title(title):
    if not title:
        return None
    t = title.lower()
    t = re.sub(r'[{}\\]', '', t)          # remove braces and backslashes (bibtex accents, etc.)
    t = re.sub(r'[^a-z0-9]+', ' ', t)      # keep only letters/numbers
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def normalize_doi(doi):
    if not doi:
        return None
    d = doi.lower().strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d)
    d = re.sub(r'^doi:\s*', '', d)
    return d.strip()


def entry_key(entry):
    """Return a unique key for comparison: prefers DOI, falls back to
    normalized title."""
    doi = normalize_doi(extract_field(entry, "doi"))
    if doi:
        return ("doi", doi)
    title = normalize_title(extract_field(entry, "title"))
    if title:
        return ("title", title)
    return None


def load_entries(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return split_entries(text)


def main():
    citations_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    citations_dir = os.path.abspath(citations_dir)

    if not os.path.isdir(citations_dir):
        print(f"Folder not found: {citations_dir}")
        sys.exit(1)

    root_dir = os.path.dirname(citations_dir)
    output_dir = os.path.join(root_dir, "2_Duplicate_Removal")
    output_path = os.path.join(output_dir, "CitationsNoDuplicates.bib")

    print(f"1_Citations folder: {citations_dir}")
    print(f"Output file: {output_path}\n")

    seen_keys = set()
    merged_entries = []
    total_per_db = {}
    added_per_db = {}

    for db in DATABASES:
        db_path = os.path.join(citations_dir, db, f"{db}.bib")
        if not os.path.isfile(db_path):
            print(f"[{db}] SKIP: file not found -> {db_path}")
            continue

        entries = load_entries(db_path)
        total_per_db[db] = len(entries)
        added = 0

        for e in entries:
            k = entry_key(e)
            if k is None:
                # No DOI and no title: keep it anyway to avoid losing data,
                # but it can never be recognized as a duplicate of anything else.
                merged_entries.append(e)
                added += 1
                continue
            if k not in seen_keys:
                seen_keys.add(k)
                merged_entries.append(e)
                added += 1

        added_per_db[db] = added
        print(f"[{db}] entries={len(entries)} added_as_new={added}")

    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(merged_entries))
        if merged_entries:
            f.write("\n")

    print(f"\nTotal unique entries: {len(merged_entries)}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()