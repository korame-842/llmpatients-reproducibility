# Public numerical evidence

Run `python3 -B experiments/run.py` from the package root (Python 3.10+).

`evidence/` contains only selected fields used by `_analysis.py`: numeric
response vectors, assignment IDs, conditions, outcome status and categorical
ratings. Free-text questions, case descriptions, prompts, model answers and
rating rationales are absent. `answer_present` records whether the private
source had a nonempty answer; it is not a replacement response. The analysis
was modified only to check that flag instead of reading the withheld answer.
Endpoint calculations and the expected numerical reference remain unchanged.

`02_missteps/turn_labels.csv` contains the 600 rater-by-turn labels (two raters,
300 turns). Detector predictions retain only turn indexes and condition codes.
`clinician_ratings/transcript_ratings.csv` contains 240 numeric scores with source
sheet/cell locations and private-workbook hashes. These are projections from
the original workbooks, not new or inferred ratings; source text and workbook
metadata are not included. The archived metric calculation now reads these CSV
projections instead of the withheld workbooks.

`01_questionnaires/results/` preserves 30 numeric answer vectors and saved
numeric scores. Original item definitions, interpretation text, severity labels,
manuals, scoring keys and norms are absent. `scoring.py` is the generic archived
scoring implementation; to use it, obtain authorized local definitions. The
public entry point does not claim to validate those missing definitions.

Hash verification cannot authenticate undistributed originals. Numerical
recomputation cannot establish semantic correctness of historical judgments.
No generation or semantic rerating is performed by the public check.
