# Final deliverables

| File | What it is |
|---|---|
| `SmartHealth_AI_Project_Report.pdf` | Project report, 27 pages, in the layout of the reference report |
| `SmartHealth_AI_Poster_A3.pdf` | A3 poster, in the layout of the reference poster |
| `SmartHealth_AI_Final_Presentation.pptx` | 13-slide project deck with speaker notes (real hardware photos, tremor module, honest limits) |
| `SmartHealth_AI_Tutorials_T1-T15.pptx` | 18-slide deck, one slide per tutorial T1 to T15, with the real figures |
| `../tutorials/` | All fifteen tutorials in one folder; `python tutorials/run_all.py` runs them |

`build/` holds the scripts that produce all of the above from the repo's own results (`models/*.json`, `tutorials/*/outputs`,
`docs/screenshots`, the two hardware photos). Rebuild: `cd final/build && npm install pptxgenjs sharp`, then
`python final/build/build_all.py` from the repo root (needs matplotlib, pillow, reportlab, plus the project venv's numpy).
The decks also want `apply_theme.js` from the pptx skill copied into `final/build/` (not committed); without it they build but with Office's default palette.
