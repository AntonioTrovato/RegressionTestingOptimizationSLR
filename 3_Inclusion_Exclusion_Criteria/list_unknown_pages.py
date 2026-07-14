"""
Lists the DOI of papers in AfterExclusionCriteria.bib whose page count
could not be determined (i.e. missing/unparseable "numpages" and "pages"
fields), so they can be checked manually against EXC-4 (short papers).

Usage:
    python list_unknown_pages.py [path_to_folder]

If no argument is given, the current directory is used
(assumed to contain AfterExclusionCriteria.bib).
"""

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


def get_page_count(entry):
    numpages = extract_field(entry, "numpages")
    if numpages:
        m = re.search(r'\d+', numpages)
        if m:
            return int(m.group(0))

    pages = extract_field(entry, "pages")
    if pages:
        p = pages.replace("–", "-").replace("—", "-")
        p = re.sub(r'-+', '-', p)
        m = re.match(r'\s*(\d+)\s*-\s*(\d+)\s*$', p)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if end >= start:
                return end - start + 1
        m = re.match(r'\s*(\d+)\s*$', p)
        if m:
            return 1

    return None


def get_entry_key_label(entry):
    """Get the BibTeX citation key (the identifier right after '@type{')."""
    m = re.match(r'@\w+\s*\{\s*([^,]+),', entry)
    return m.group(1).strip() if m else "UNKNOWN_KEY"


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    folder = os.path.abspath(folder)
    input_path = os.path.join(folder, "AfterExclusionCriteria.bib")

    if not os.path.isfile(input_path):
        print(f"File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    unknown = []
    for e in entries:
        if get_page_count(e) is None:
            doi = extract_field(e, "doi")
            key = get_entry_key_label(e)
            unknown.append((key, doi))

    print(f"Total entries: {len(entries)}")
    print(f"Entries with undeterminable page count: {len(unknown)}\n")

    for key, doi in unknown:
        if doi:
            print(doi)
        else:
            print(f"[NO DOI] (bibtex key: {key})")


if __name__ == "__main__":
    main()