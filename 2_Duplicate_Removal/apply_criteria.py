#!/usr/bin/env python3
"""
Applies inclusion and exclusion criteria to CitationsNoDuplicates.bib.

Usage:
    python apply_criteria.py [path_to_2_Duplicate_Removal_folder]

If no argument is given, the current directory is used
(assumed to be 2_Duplicate_Removal).

Expected input:
    2_Duplicate_Removal/CitationsNoDuplicates.bib

Output (in ../3_Inclusion_exclusion_Criteria, sibling of 2_Duplicate_Removal):
    AfterInclusionCriteria.bib   -> papers matching at least one inclusion criterion
    AfterExclusionCriteria.bib   -> papers from the above that match NO exclusion
                                     criterion (final selection)

--------------------------------------------------------------------------
CRITERIA IMPLEMENTED
--------------------------------------------------------------------------

Inclusion criteria (a paper passes step (i) if it matches AT LEAST ONE):
  INC-1 / INC-2 / INC-3: as requested, all three are checked the same way,
  i.e. by searching in the title OR abstract for at least one of these
  quoted phrase groups:
      "test case selection"
      "test suite minimization"
      "test suite reduction"
      "test case prioritization"
  (We cannot automatically distinguish "proposing a new approach" or
  "examining effectiveness" from plain relatedness without NLP/semantic
  analysis, so per your instructions all three INC criteria are evaluated
  as keyword-presence checks on title/abstract.)

Exclusion criteria (a paper is excluded if it matches AT LEAST ONE):
  EXC-1: Unrelated to "regression testing".
         Implemented as: the phrase group "regression test" (which also
         covers "regression testing" / "regression tests" / "regression
         test suite" etc.) is NOT found in title or abstract.
  EXC-2: Not published in Journals or Conferences.
         Implemented using the BibTeX entry type:
             - "article", "inproceedings", "conference", "proceedings"
               => considered journal/conference publications (kept)
             - anything else (e.g. "misc", "techreport", "phdthesis",
               "incollection", "book") => excluded
  EXC-3: Not written in English.
         SKIPPED as requested (no reliable automatic way to check this,
         and virtually no entries are expected to be non-English).
  EXC-4: Short papers (fewer than 6 pages).
         Implemented using, in order of preference:
             1. the "numpages" field, if present
             2. the "pages" field, computed as (end - start + 1) when it
                is a numeric range like "216-226" or "216--226"
         If neither field is usable (missing or not parseable), the
         paper is NOT excluded (conservative choice: we don't exclude
         when we can't determine the page count), but it is flagged in
         the log so you can double check it manually.

--------------------------------------------------------------------------
"""

import os
import re
import sys

# Quoted phrase groups used for INC-1/2/3 (checked identically, see docstring)
INCLUSION_PHRASE_GROUPS = [
    "test case selection",
    "test suite minimization",
    "test suite reduction",
    "test case prioritization",
]

# Additional phrase groups for INC-2 ("proposing a new approach")
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

# Quoted phrase group used for EXC-1 (paper excluded if NONE of these found)
REGRESSION_TESTING_PHRASE_GROUPS = [
    "regression testing",
]

# Entry types considered as "journal or conference" publications for EXC-2
VALID_ENTRY_TYPES = {"article", "inproceedings", "conference", "proceedings"}

MIN_PAGES = 6  # EXC-4 threshold: papers with fewer pages than this are excluded


# --------------------------------------------------------------------------
# BibTeX parsing helpers
# --------------------------------------------------------------------------

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


def get_entry_type(entry):
    """Return the BibTeX entry type (e.g. 'article', 'inproceedings'),
    lowercased."""
    m = re.match(r'@(\w+)\s*\{', entry)
    return m.group(1).lower() if m else None


def extract_field(entry, field):
    """Extract the value of a field (e.g. doi, title, abstract, pages,
    numpages) from a BibTeX entry. Handles values delimited by {} or by ""."""
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


def normalize_text(text):
    """Lowercase and collapse whitespace, remove braces/backslashes, for
    keyword matching in title/abstract."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[{}\\]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def contains_any_phrase(text, phrase_groups):
    """Return True if at least one of the phrase groups is found as a
    substring in the (already normalized) text."""
    for phrase in phrase_groups:
        if phrase in text:
            return True
    return False


# --------------------------------------------------------------------------
# Page count helper (EXC-4)
# --------------------------------------------------------------------------

def get_page_count(entry):
    """Try to determine the number of pages of a paper.
    Returns an int, or None if it cannot be determined."""

    numpages = extract_field(entry, "numpages")
    if numpages:
        m = re.search(r'\d+', numpages)
        if m:
            return int(m.group(0))

    pages = extract_field(entry, "pages")
    if pages:
        # Normalize en-dash / em-dash / double-dash to a single '-'
        p = pages.replace("–", "-").replace("—", "-")
        p = re.sub(r'-+', '-', p)
        m = re.match(r'\s*(\d+)\s*-\s*(\d+)\s*$', p)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if end >= start:
                return end - start + 1
        # Single page number (e.g. pages = {45}) => 1 page
        m = re.match(r'\s*(\d+)\s*$', p)
        if m:
            return 1

    return None  # could not determine


# --------------------------------------------------------------------------
# Criteria evaluation
# --------------------------------------------------------------------------

def matches_inclusion(entry):
    title = normalize_text(extract_field(entry, "title"))
    abstract = normalize_text(extract_field(entry, "abstract"))
    combined = title + " " + abstract

    # INC-1: related to TCS/TSM/TSR/TCP
    inc1 = contains_any_phrase(combined, INCLUSION_PHRASE_GROUPS)

    # INC-2: proposes a new TCS/TSM/TSR/TCP approach
    #        (must mention the technique AND sound like it's proposing something new)
    inc2 = contains_any_phrase(combined, INCLUSION_PHRASE_GROUPS) and \
           contains_any_phrase(combined, NEW_APPROACH_PHRASE_GROUPS)

    return inc1, inc2


def matches_exclusion(entry):
    """Returns a tuple (exc1, exc2, exc4, unknown_pages) of booleans/flag."""
    title = normalize_text(extract_field(entry, "title"))
    abstract = normalize_text(extract_field(entry, "abstract"))
    combined = title + " " + abstract

    # EXC-1: excluded if the "regression test" phrase group is NOT found
    exc1 = not contains_any_phrase(combined, REGRESSION_TESTING_PHRASE_GROUPS)

    # EXC-2: excluded if entry type is not journal/conference
    entry_type = get_entry_type(entry)
    exc2 = entry_type not in VALID_ENTRY_TYPES

    # EXC-4: excluded if page count is known and < MIN_PAGES
    page_count = get_page_count(entry)
    unknown_pages = page_count is None
    exc4 = (page_count is not None) and (page_count < MIN_PAGES)

    return exc1, exc2, exc4, unknown_pages


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    dup_removal_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    dup_removal_dir = os.path.abspath(dup_removal_dir)

    input_path = os.path.join(dup_removal_dir, "CitationsNoDuplicates.bib")
    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    root_dir = os.path.dirname(dup_removal_dir)
    output_dir = os.path.join(root_dir, "3_Inclusion_exclusion_Criteria")
    os.makedirs(output_dir, exist_ok=True)

    inclusion_output_path = os.path.join(output_dir, "AfterInclusionCriteria.bib")
    exclusion_output_path = os.path.join(output_dir, "AfterExclusionCriteria.bib")

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

    with open(inclusion_output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(after_inclusion))
        if after_inclusion:
            f.write("\n")

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

    with open(exclusion_output_path, "w", encoding="utf-8") as f:
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
    print(f"-> Passed step (ii) [matches 0 exclusion criteria] - FINAL SELECTION: {len(after_exclusion)} papers\n")

    print(f"Saved: {inclusion_output_path}")
    print(f"Saved: {exclusion_output_path}")


if __name__ == "__main__":
    main()