#!/usr/bin/env python3
"""
Classifies each paper in SnowballedAfterExclusion.bib as SLR, RW, or PS,
based on keywords found in the title or abstract, and writes the result
to ClassifiedSnowballedPapers.bib (same logic as classify_studies.py,
adapted for the snowballing round).

Usage:
    python classify_snowballing_studies.py [path_to_5_Snowballing_folder]

If no argument is given, the current directory is used
(assumed to be 5_Snowballing).

Expected input:
    5_Snowballing/SnowballedAfterExclusion.bib

Output:
    5_Snowballing/ClassifiedSnowballedPapers.bib

--------------------------------------------------------------------------
CLASSIFICATION RULES (checked on title OR abstract, in this priority order)
--------------------------------------------------------------------------
  SLR: contains "systematic literature review"
  RW : contains "survey", "review" (but NOT as part of "systematic
       literature review", already handled above), "mapping study",
       or "interview"
  PS : none of the above (primary study)
--------------------------------------------------------------------------
"""

import os
import re
import sys

SLR_PHRASE = "systematic literature review"

RW_PHRASES = [
    "survey",
    "review",
    "mapping study",
    "interview",
]


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


def normalize_text(text):
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[{}\\]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def classify(entry):
    title = normalize_text(extract_field(entry, "title"))
    abstract = normalize_text(extract_field(entry, "abstract"))
    combined = title + " " + abstract

    if SLR_PHRASE in combined:
        return "SLR"

    combined_no_slr = combined.replace(SLR_PHRASE, " ")

    for phrase in RW_PHRASES:
        if phrase in combined_no_slr:
            return "RW"

    return "PS"


def add_classification_field(entry, classification):
    entry = entry.rstrip()

    if not entry.endswith("}"):
        return entry + f",\nclassification = {{{classification}}}\n}}"

    body = entry[:-1].rstrip()
    if body.endswith(","):
        body = body[:-1]

    return body + f",\nclassification = {{{classification}}}\n}}"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    snowball_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    snowball_dir = os.path.abspath(snowball_dir)

    input_path = os.path.join(snowball_dir, "SnowballedAfterExclusion.bib")
    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    output_path = os.path.join(snowball_dir, "ClassifiedSnowballedPapers.bib")

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    print(f"Input file: {input_path}")
    print(f"Total entries loaded: {len(entries)}\n")

    counts = {"SLR": 0, "RW": 0, "PS": 0}
    classified_entries = []

    for e in entries:
        classification = classify(e)
        counts[classification] += 1
        classified_entries.append(add_classification_field(e, classification))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(classified_entries))
        if classified_entries:
            f.write("\n")

    print("=== CLASSIFICATION RESULTS ===")
    print(f"SLR (systematic literature reviews): {counts['SLR']} papers")
    print(f"RW  (surveys / reviews / mapping studies / interviews): {counts['RW']} papers")
    print(f"PS  (primary studies): {counts['PS']} papers")
    print(f"Total: {len(entries)} papers\n")

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()