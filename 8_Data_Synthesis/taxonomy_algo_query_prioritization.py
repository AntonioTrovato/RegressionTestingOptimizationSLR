#!/usr/bin/env python3
import argparse
import glob
import math
import os
import re
import pandas as pd
from collections import defaultdict

# Column indices (zero-based)
COL_Y  = 24  # paper type
COL_Z  = 25  # method (prioritization/selection/both)
COL_AA = 26  # taxonomy class (possibly multi)
COL_AB = 27  # algorithm families (possibly multi)
COL_AC = 28  # number of objectives (text or number)

# Matching substrings (all lowercase)
TAXONOMY_KEYS = ["coverage", "requirement", "probability", "distribution",
                 "human", "clustering", "history", "model", "cost", "other"]
ALGO_KEYS = ["heuristic", "meta", "graph", "dynamic", "ml", "greedy"]

def first_xlsx_in_cwd():
    files = sorted(glob.glob("*.xlsx")) + sorted(glob.glob("*.xls"))
    return files[0] if files else None

def is_empty(x):
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    return str(x).strip() == ""

def split_multi(raw):
    """Split multi-valued cells on common separators."""
    if is_empty(raw):
        return []
    s = str(raw).replace("＆", "&")
    parts = re.split(r"[;,\|/+\u00B7&]+", s)  # ; , | / + · &
    return [p.strip() for p in parts if p.strip()]

def match_taxonomy_labels(cell_value):
    s = "" if is_empty(cell_value) else str(cell_value).lower()
    tokens = split_multi(s) or [s]
    found = set()
    for tok in tokens:
        lt = tok.lower()
        for key in TAXONOMY_KEYS:
            if key in lt:
                found.add(key)
    return found

def match_algorithm_labels(cell_value):
    """
    'heuristic' should exclude tokens that contain 'meta'.
    'meta' matches metaheuristics.
    'ml' matches 'ml' or 'machine learning'.
    """
    s = "" if is_empty(cell_value) else str(cell_value).lower()
    tokens = split_multi(s) or [s]
    found = set()
    for tok in tokens:
        lt = tok.lower()
        if "meta" in lt:  # metaheuristic, meta-*, etc.
            found.add("meta")
        if "heuristic" in lt and "meta" not in lt:
            found.add("heuristic")
        if "graph" in lt:
            found.add("graph")
        if "dynamic" in lt:
            found.add("dynamic")
        if "ml" in lt or "machine learning" in lt:
            found.add("ml")
        if "greedy" in lt:
            found.add("greedy")
    return found

def parse_objectives(cell_value):
    """
    Return None if AC is empty; else 'one' or 'multi'.
    Substrings accepted: one, multu/multi, two, three; numbers >=2 => multi.
    """
    if is_empty(cell_value):
        return None
    s = str(cell_value).strip().lower()
    if "one" in s or "single" in s or s == "1":
        return "one"
    if "multu" in s or "multi" in s:
        return "multi"
    if "two" in s or "three" in s:
        return "multi"
    nums = re.findall(r"\d+", s)
    for n in nums:
        try:
            v = int(n)
            if v >= 2:
                return "multi"
            if v == 1:
                return "one"
        except:
            pass
    # weak hints
    if "objectives" in s or ">" in s:
        return "multi"
    return "one"

def paper_id_from_index(idx0):
    # Excel data row = idx0 + 2; i = row - 1 = idx0 + 1
    return f"paper_{idx0 + 1}"

def load_df(path):
    df = pd.read_excel(path, header=0)
    if df.shape[1] < (COL_AC + 1):
        df = pd.read_excel(path, header=None)
    return df

def filter_ps_prioritization(df):
    result = []
    for idx, row in df.iterrows():
        try:
            y = row.iloc[COL_Y]
            z = row.iloc[COL_Z]
        except Exception:
            continue
        if str(y).strip() != "PS":
            continue
        z_str = "" if is_empty(z) else str(z).lower()
        if "prioritization" not in z_str:
            continue
        result.append((idx, row))
    return result

def build_pairs(filtered_rows):
    """
    Returns:
      pair_map: dict[(taxonomy, algorithm)] -> sorted unique list of paper_ids
      obj_map:  dict[paper_id] -> None/'one'/'multi'
    """
    pair_map = defaultdict(list)
    obj_map = {}
    for idx, row in filtered_rows:
        pid = paper_id_from_index(idx)
        try:
            aa = row.iloc[COL_AA]
            ab = row.iloc[COL_AB]
            ac = row.iloc[COL_AC]
        except Exception:
            continue
        taxos = match_taxonomy_labels(aa)
        algos = match_algorithm_labels(ab)
        obj_map[pid] = parse_objectives(ac)
        if not taxos or not algos:
            continue
        for t in taxos:
            for a in algos:
                pair_map[(t, a)].append(pid)

    # deduplicate and sort paper ids numerically
    for k, v in pair_map.items():
        uniq = sorted(set(v), key=lambda x: int(x.split("_")[1]))
        pair_map[k] = uniq
    return pair_map, obj_map

def main():
    ap = argparse.ArgumentParser(description="List (taxonomy, algorithm) -> paper_i (with [multi-obj] tags).")
    ap.add_argument("-i", "--input", help="Excel file (default: first .xlsx in folder)")
    args = ap.parse_args()

    in_path = args.input or first_xlsx_in_cwd()
    if not in_path or not os.path.exists(in_path):
        raise FileNotFoundError("No Excel file found. Put it here or pass with -i <file.xlsx>.")

    df = load_df(in_path)
    filtered = filter_ps_prioritization(df)
    pair_map, obj_map = build_pairs(filtered)

    # Order output by taxonomy then algorithm (alphabetical)
    pairs = [(t, a) for (t, a) in pair_map.keys() if pair_map[(t, a)]]
    pairs.sort(key=lambda x: (x[0], x[1]))

    # Print as numbered list
    for idx, (t, a) in enumerate(pairs, start=1):
        papers = pair_map[(t, a)]
        decorated = []
        for pid in papers:
            obj = obj_map.get(pid)
            if obj is not None and obj == "multi":
                decorated.append(f"{pid} [multi-obj]")
            else:
                decorated.append(pid)
        count = len(papers)
        print(f"{idx}.")
        print(f"({t}, {a}) [{count}] = " + ", ".join(decorated))

if __name__ == "__main__":
    main()
