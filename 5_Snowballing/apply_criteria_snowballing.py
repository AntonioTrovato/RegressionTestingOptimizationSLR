#!/usr/bin/env python3
"""
Applies inclusion and exclusion criteria to SnowballedPapersNoDuplicates.bib
(same logic as apply_criteria.py, adapted for the snowballing round).

Usage:
    python apply_criteria_snowballing.py [path_to_5_Snowballing_folder]

If no argument is given, the current directory is used
(assumed to be 5_Snowballing).

Expected input:
    5_Snowballing/SnowballedPapersNoDuplicates.bib

Output:
    5_Snowballing/SnowballedAfterExclusion.bib   -> final selection: papers
        that matched at least one inclusion criterion AND matched no
        exclusion criterion

--------------------------------------------------------------------------
CRITERIA (identical to apply_criteria.py)
--------------------------------------------------------------------------
INC-1: title/abstract contains one of "test case selection",
       "test suite minimization", "test suite reduction",
       "test case prioritization"
INC-2: INC-1 terms AND a "proposes a new approach" style phrase
       (propose/proposes/proposed, new approach, novel approach/method,
       we present, this paper presents)
INC-3: skipped (as in the original script)

EXC-1: excluded if "regression testing" is NOT found in title/abstract
EXC-2: excluded if entry type is not article/inproceedings/conference/proceedings
EXC-3: skipped (not written in English) - not automatically checkable
EXC-4: excluded if page count (numpages, else pages range) is known and < 6
       (if page count cannot be determined, the paper is NOT excluded,
       but flagged in the log)
--------------------------------------------------------------------------
"""

import os
import re
import sys

INCLUSION_PHRASE_GROUPS = [
    "test case selection",
    "test suite minimization",
    "test suite reduction",
    "test case prioritization",
]

NEW_APPROACH_PHRASE_GROUPS = [
    "propose",
    "proposes",
    "proposed",
    "new approach",
    "novel approach",
    "novel method",
    "we present",
    "this paper presents",
]

REGRESSION_TESTING_PHRASE_GROUPS = [
    "regression testing",
]

VALID_ENTRY_TYPES = {"article", "inproceedings", "conference", "proceedings"}

MIN_PAGES = 6


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


def normalize_text(text):
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[{}\\]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def contains_any_phrase(text, phrase_groups):
    for phrase in phrase_groups:
        if phrase in text:
            return True
    return False


# --------------------------------------------------------------------------
# Page count helper (EXC-4)
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Criteria evaluation
# --------------------------------------------------------------------------

def matches_inclusion(entry):
    title = normalize_text(extract_field(entry, "title"))
    abstract = normalize_text(extract_field(entry, "abstract"))
    combined = title + " " + abstract

    inc1 = contains_any_phrase(combined, INCLUSION_PHRASE_GROUPS)
    inc2 = contains_any_phrase(combined, INCLUSION_PHRASE_GROUPS) and \
           contains_any_phrase(combined, NEW_APPROACH_PHRASE_GROUPS)

    return inc1, inc2


def matches_exclusion(entry):
    title = normalize_text(extract_field(entry, "title"))
    abstract = normalize_text(extract_field(entry, "abstract"))
    combined = title + " " + abstract

    exc1 = not contains_any_phrase(combined, REGRESSION_TESTING_PHRASE_GROUPS)

    entry_type = get_entry_type(entry)
    exc2 = entry_type not in VALID_ENTRY_TYPES

    page_count = get_page_count(entry)
    unknown_pages = page_count is None
    exc4 = (page_count is not None) and (page_count < MIN_PAGES)

    return exc1, exc2, exc4, unknown_pages


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    snowball_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    snowball_dir = os.path.abspath(snowball_dir)

    input_path = os.path.join(snowball_dir, "SnowballedPapersNoDuplicates.bib")
    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    output_path = os.path.join(snowball_dir, "SnowballedAfterExclusion.bib")

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    print(f"Input file: {input_path}")
    print(f"Total entries loaded: {len(entries)}\n")

    # ---------------- Step (i): Inclusion criteria ----------------
    inc1_count = 0
    inc2_count = 0
    after_inclusion = []

    for e in entries:
        inc1, inc2 = matches_inclusion(e)
        if inc1:
            inc1_count += 1
        if inc2:
            inc2_count += 1
        if inc1 or inc2:
            after_inclusion.append(e)

    # ---------------- Step (ii): Exclusion criteria ----------------
    exc1_count = 0
    exc2_count = 0
    exc4_count = 0
    unknown_pages_count = 0
    after_exclusion = []

    for e in after_inclusion:
        exc1, exc2, exc4, unknown_pages = matches_exclusion(e)
        if exc1:
            exc1_count += 1
        if exc2:
            exc2_count += 1
        if exc4:
            exc4_count += 1
        if unknown_pages:
            unknown_pages_count += 1
        if not (exc1 or exc2 or exc4):
            after_exclusion.append(e)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(after_exclusion))
        if after_exclusion:
            f.write("\n")

    # ---------------- Statistics ----------------
    print("=== INCLUSION CRITERIA (evaluated on all", len(entries), "entries) ===")
    print(f"INC-1 (related to TCS/TSM/TSR/TCP terms): {inc1_count} papers")
    print(f"INC-2 (proposes a new TCS/TSM/TSR/TCP approach): {inc2_count} papers")
    print("INC-3 (examining effectiveness): SKIPPED as requested")
    print(f"-> Passed step (i) [matches >= 1 inclusion criterion]: {len(after_inclusion)} papers\n")

    print("=== EXCLUSION CRITERIA (evaluated on the", len(after_inclusion), "papers from step (i)) ===")
    print(f"EXC-1 (unrelated to 'regression testing'): {exc1_count} papers")
    print(f"EXC-2 (not journal/conference publication): {exc2_count} papers")
    print("EXC-3 (not written in English): SKIPPED as requested")
    print(f"EXC-4 (short papers, < {MIN_PAGES} pages): {exc4_count} papers")
    if unknown_pages_count:
        print(f"  (note: {unknown_pages_count} papers had an undeterminable "
              f"page count and were NOT excluded by EXC-4 - please check manually)")
    print(f"-> Passed step (ii) [matches 0 exclusion criteria] - FINAL SNOWBALLING SELECTION: {len(after_exclusion)} papers\n")

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()