#!/usr/bin/env python3
"""
Merges NewSnowballedPapers.bib with the existing corpus (ClassifiedStudies.bib)
for deduplication purposes only: papers already present in the corpus (matched
by DOI or normalized title) are REMOVED from the snowballing output. Papers
that are duplicated among themselves within NewSnowballedPapers.bib are also
deduplicated (first occurrence kept).

The final output does NOT include any paper from the original corpus - it
only contains the genuinely NEW candidate papers found via snowballing.

Usage:
    python merge_no_snowballing_duplicates.py [path_to_5_Snowballing_folder]

If no argument is given, the current directory is used
(assumed to be 5_Snowballing).

Expected input:
    5_Snowballing/NewSnowballedPapers.bib
    ../4_Classification/ClassifiedStudies.bib

Output:
    5_Snowballing/SnowballedPapersNoDuplicates.bib
"""

import os
import re
import sys


# --------------------------------------------------------------------------
# BibTeX parsing helpers (same approach as the other scripts)
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


def normalize_title(title):
    if not title:
        return None
    t = title.lower()
    t = re.sub(r'[{}\\]', '', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def normalize_doi(doi):
    if not doi:
        return None
    d = doi.lower().strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d)
    d = re.sub(r'^doi:\s*', '', d)
    return d.strip()


def entry_keys(entry):
    """Return a set of keys usable to match this entry against others:
    ("doi", ...) if a DOI is available, ("title", ...) if a title is
    available. A single entry can therefore be matched via either."""
    keys = set()
    doi = normalize_doi(extract_field(entry, "doi"))
    if doi:
        keys.add(("doi", doi))
    title = normalize_title(extract_field(entry, "title"))
    if title:
        keys.add(("title", title))
    return keys


def load_entries(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return split_entries(text)


def main():
    snowball_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    snowball_dir = os.path.abspath(snowball_dir)

    snowball_path = os.path.join(snowball_dir, "NewSnowballedPapers.bib")
    root_dir = os.path.dirname(snowball_dir)
    corpus_path = os.path.join(root_dir, "4_Classification", "ClassifiedStudies.bib")
    output_path = os.path.join(snowball_dir, "SnowballedPapersNoDuplicates.bib")

    if not os.path.isfile(snowball_path):
        print(f"File not found: {snowball_path}")
        sys.exit(1)
    if not os.path.isfile(corpus_path):
        print(f"File not found: {corpus_path}")
        sys.exit(1)

    print(f"Snowballing candidates: {snowball_path}")
    print(f"Existing corpus:        {corpus_path}")
    print(f"Output:                 {output_path}\n")

    corpus_entries = load_entries(corpus_path)
    snowball_entries = load_entries(snowball_path)

    # Build the set of all keys (doi/title) already present in the corpus
    corpus_keys = set()
    for e in corpus_entries:
        corpus_keys |= entry_keys(e)

    print(f"Corpus entries: {len(corpus_entries)}")
    print(f"Snowballing candidate entries: {len(snowball_entries)}\n")

    kept_entries = []
    seen_keys = set()  # keys already kept among snowballing candidates
    skipped_in_corpus = 0
    skipped_internal_duplicate = 0

    for e in snowball_entries:
        keys = entry_keys(e)

        # Already present in the original corpus -> drop
        if keys & corpus_keys:
            skipped_in_corpus += 1
            continue

        # Duplicate among the snowballing candidates themselves -> drop
        if keys and (keys & seen_keys):
            skipped_internal_duplicate += 1
            continue

        kept_entries.append(e)
        seen_keys |= keys

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(kept_entries))
        if kept_entries:
            f.write("\n")

    print("=== RESULTS ===")
    print(f"Already in the original corpus (removed): {skipped_in_corpus}")
    print(f"Duplicate among snowballing candidates (removed): {skipped_internal_duplicate}")
    print(f"NEW unique papers kept: {len(kept_entries)}")
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()