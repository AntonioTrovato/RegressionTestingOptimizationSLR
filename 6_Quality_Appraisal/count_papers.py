#!/usr/bin/env python3
"""
Quick paper counter for NewSnowballedPapers.bib.

Usage:
    python count_papers.py [path_to_5_Snowballing_folder]

If no argument is given, the current directory is used.
"""

import os
import re
import sys

folder = sys.argv[1] if len(sys.argv) > 1 else "."
path = os.path.join(os.path.abspath(folder), "QualityAppraisal.bib")

if not os.path.isfile(path):
    print(f"File not found: {path}")
    sys.exit(1)

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

count = len(re.findall(r'@\w+\s*\{', text))
print(f"{count} papers in {path}")