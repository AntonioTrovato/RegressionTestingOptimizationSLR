#!/usr/bin/env python3
"""
Forward and backward snowballing using the OpenAlex API (free, no API key
required). For every paper in ClassifiedStudies.bib:
  - BACKWARD snowballing: papers it references (its bibliography)
  - FORWARD snowballing:  papers that cite it

New papers (not already present in your corpus, matched by DOI) are
collected, deduplicated, and written as a .bib file so you can feed them
into your existing duplicate-removal / inclusion-exclusion scripts.

Usage:
    python snowball.py [path_to_4_Classification_folder] [--email you@example.com]

If no path is given, the current directory is used
(assumed to be 4_Classification).

The --email flag is optional but recommended: OpenAlex gives faster,
more reliable service to requests that identify a contact email
("polite pool"). It is NOT stored anywhere except sent as a query param.

Expected input:
    4_Classification/ClassifiedStudies.bib

Output (in ../5_Snowballing, sibling of 4_Classification):
    NewSnowballedPapers.bib

Notes / limitations:
  - Requires internet access and only uses the Python standard library
    (urllib), so no virtual environment / pip install needed.
  - OpenAlex coverage is very good but not 100%: some old or obscure
    papers may not be indexed, or may be missing some references/citations.
  - This script only DISCOVERS new candidate papers. You still need to
    run your existing duplicate-removal and inclusion/exclusion scripts
    on the output (merging it with your current corpus) to get the final
    snowballing round.
  - Rate limiting: the script sleeps briefly between requests to stay
    well within OpenAlex's rate limits. For large corpora this can take
    a while - progress is printed as it goes.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

OPENALEX_BASE = "https://api.openalex.org"
REQUEST_DELAY = 0.15  # seconds between requests (polite pool allows ~10/sec)
BATCH_SIZE = 50        # OpenAlex allows filtering by up to ~50 IDs per request


# --------------------------------------------------------------------------
# BibTeX parsing helpers (same approach as your other scripts)
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


def normalize_doi(doi):
    if not doi:
        return None
    d = doi.lower().strip()
    d = re.sub(r'^https?://(dx\.)?doi\.org/', '', d)
    d = re.sub(r'^doi:\s*', '', d)
    return d.strip()


def bib_escape(text):
    """Very light escaping for values placed inside {...} in BibTeX."""
    if not text:
        return ""
    return text.replace("{", "(").replace("}", ")")


# --------------------------------------------------------------------------
# OpenAlex API helpers
# --------------------------------------------------------------------------

def api_get(url):
    """GET a URL and return parsed JSON, with basic retry on transient errors."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SLR-Snowballing-Script/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(REQUEST_DELAY)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"  HTTP error {e.code} on attempt {attempt + 1}, retrying...")
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            print(f"  Error ({e}) on attempt {attempt + 1}, retrying...")
            time.sleep(1.5 * (attempt + 1))
    return None


def build_url(path, params):
    query = urllib.parse.urlencode(params)
    return f"{OPENALEX_BASE}{path}?{query}"


def get_work_by_doi(doi, email=None):
    params = {}
    if email:
        params["mailto"] = email
    encoded_doi = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
    url = build_url(f"/works/doi:{doi}", params)
    return api_get(url)


def get_citing_works(openalex_id, email=None):
    """Return the list of works that cite the given OpenAlex work ID."""
    results = []
    cursor = "*"
    params_base = {"filter": f"cites:{openalex_id}", "per-page": 200}
    if email:
        params_base["mailto"] = email

    while cursor:
        params = dict(params_base)
        params["cursor"] = cursor
        url = build_url("/works", params)
        data = api_get(url)
        if not data:
            break
        results.extend(data.get("results", []))
        cursor = data.get("meta", {}).get("next_cursor")
        if not data.get("results"):
            break
    return results


def get_works_by_ids(openalex_ids, email=None):
    """Fetch metadata for a list of OpenAlex work IDs, in batches."""
    all_results = []
    ids = list(openalex_ids)
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        short_ids = [b.split("/")[-1] for b in batch]
        params = {"filter": "openalex_id:" + "|".join(short_ids), "per-page": 200}
        if email:
            params["mailto"] = email
        url = build_url("/works", params)
        data = api_get(url)
        if data:
            all_results.extend(data.get("results", []))
        print(f"  Fetched metadata batch {i // BATCH_SIZE + 1} "
              f"({min(i + BATCH_SIZE, len(ids))}/{len(ids)})")
    return all_results


def reconstruct_abstract(inverted_index):
    """OpenAlex stores abstracts as {word: [positions]}. Rebuild plain text."""
    if not inverted_index:
        return ""
    position_word = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word
    if not position_word:
        return ""
    max_pos = max(position_word.keys())
    words = [position_word.get(p, "") for p in range(max_pos + 1)]
    return " ".join(words)


def openalex_type_to_bibtex(work):
    """Map OpenAlex 'type' to a BibTeX entry type consistent with your
    other scripts (article / inproceedings / misc)."""
    t = (work.get("type") or "").lower()
    if t == "article":
        return "article"
    if t in ("proceedings-article",):
        return "inproceedings"
    if t in ("book-chapter",):
        return "incollection"
    return "misc"


def work_to_bibtex(work, cite_key):
    doi = normalize_doi(work.get("doi"))
    title = work.get("display_name") or work.get("title") or "Untitled"
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    year = work.get("publication_year") or ""
    entry_type = openalex_type_to_bibtex(work)

    biblio = work.get("biblio") or {}
    first_page = biblio.get("first_page")
    last_page = biblio.get("last_page")
    pages_field = ""
    if first_page and last_page:
        pages_field = f"pages = {{{first_page}-{last_page}}},\n"

    venue = ""
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    if source.get("display_name"):
        venue = source["display_name"]

    lines = [f"@{entry_type}{{{cite_key},"]
    lines.append(f"title = {{{bib_escape(title)}}},")
    if abstract:
        lines.append(f"abstract = {{{bib_escape(abstract)}}},")
    if doi:
        lines.append(f"doi = {{{doi}}},")
    if year:
        lines.append(f"year = {{{year}}},")
    if venue:
        field_name = "journal" if entry_type == "article" else "booktitle"
        lines.append(f"{field_name} = {{{bib_escape(venue)}}},")
    if pages_field:
        lines.append(pages_field.rstrip(",\n") + ",")
    lines.append("note = {Found via snowballing (OpenAlex)}")
    lines.append("}")
    return "\n".join(lines)


def make_cite_key(work, index):
    doi = normalize_doi(work.get("doi"))
    if doi:
        safe = re.sub(r'[^a-zA-Z0-9]', '', doi)
        return f"snowball_{safe[:40]}"
    return f"snowball_{index}"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    email = None
    if "--email" in args:
        idx = args.index("--email")
        email = args[idx + 1]
        del args[idx:idx + 2]

    classification_dir = args[0] if args else "."
    classification_dir = os.path.abspath(classification_dir)

    input_path = os.path.join(classification_dir, "ClassifiedStudies.bib")
    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    root_dir = os.path.dirname(classification_dir)
    output_dir = os.path.join(root_dir, "5_Snowballing")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "NewSnowballedPapers.bib")

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = split_entries(text)

    known_dois = set()
    for e in entries:
        d = normalize_doi(extract_field(e, "doi"))
        if d:
            known_dois.add(d)

    print(f"Input file: {input_path}")
    print(f"Corpus size: {len(entries)} papers ({len(known_dois)} with a usable DOI)\n")

    # ---------------- Step 1: resolve each paper to its OpenAlex ID ----------------
    candidate_ids = set()  # OpenAlex IDs of newly discovered candidate papers
    resolved = 0
    unresolved = 0

    for i, e in enumerate(entries, 1):
        doi = normalize_doi(extract_field(e, "doi"))
        if not doi:
            continue

        print(f"[{i}/{len(entries)}] Resolving DOI {doi} ...")
        work = get_work_by_doi(doi, email=email)
        if not work:
            unresolved += 1
            continue
        resolved += 1

        openalex_id = work.get("id")

        # BACKWARD: referenced works (this paper's bibliography)
        referenced = work.get("referenced_works") or []
        candidate_ids.update(referenced)

        # FORWARD: works that cite this paper
        citing_works = get_citing_works(openalex_id, email=email)
        for w in citing_works:
            if w.get("id"):
                candidate_ids.add(w["id"])

        print(f"  backward: {len(referenced)} references | "
              f"forward: {len(citing_works)} citing papers | "
              f"running total candidates: {len(candidate_ids)}")

    print(f"\nResolved {resolved}/{len(entries)} papers on OpenAlex "
          f"({unresolved} not found / no DOI).")
    print(f"Total unique candidate OpenAlex IDs collected: {len(candidate_ids)}\n")

    # ---------------- Step 2: fetch metadata for all candidates ----------------
    print("Fetching metadata for candidate papers...")
    candidate_works = get_works_by_ids(candidate_ids, email=email)

    # ---------------- Step 3: filter out papers already in the corpus ----------------
    new_entries = []
    seen_new_dois = set()
    skipped_already_known = 0
    skipped_no_doi_duplicate = 0

    for i, work in enumerate(candidate_works):
        doi = normalize_doi(work.get("doi"))
        if doi and doi in known_dois:
            skipped_already_known += 1
            continue
        if doi:
            if doi in seen_new_dois:
                skipped_no_doi_duplicate += 1
                continue
            seen_new_dois.add(doi)

        cite_key = make_cite_key(work, i)
        new_entries.append(work_to_bibtex(work, cite_key))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(new_entries))
        if new_entries:
            f.write("\n")

    print("\n=== SNOWBALLING RESULTS ===")
    print(f"Candidate papers found (backward + forward, deduplicated): {len(candidate_works)}")
    print(f"Already in your corpus (skipped): {skipped_already_known}")
    print(f"Duplicate among candidates (skipped): {skipped_no_doi_duplicate}")
    print(f"NEW papers written to output: {len(new_entries)}")
    print(f"\nSaved: {output_path}")
    print("\nNext steps: run this file through your duplicate-removal and "
          "inclusion/exclusion scripts (as a 5th 'database') to get the "
          "final list of papers to add from this snowballing round.")


if __name__ == "__main__":
    main()