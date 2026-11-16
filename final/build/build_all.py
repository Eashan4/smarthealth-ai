"""Rebuild every deliverable in final/: figures, report, poster, both decks.
Needs: python with matplotlib, pillow, reportlab, python-pptx not required; node with pptxgenjs and sharp
(cd final/build && npm install pptxgenjs sharp). Run from the repo root:  python final/build/build_all.py"""
import subprocess, sys
from pathlib import Path
B = Path(__file__).resolve().parent
for cmd in ([sys.executable, "make_assets.py"], [sys.executable, "build_report.py"], [sys.executable, "build_poster.py"],
            ["node", "build_project_deck.js"], ["node", "build_tutorial_deck.js"]):
    print("->", " ".join(cmd)); subprocess.run(cmd, cwd=B, check=True)
