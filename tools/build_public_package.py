"""Build the public numerical-replication edition from the private review ZIP.

Modified distribution, 2026-10-27. Code: AGPL-3.0, as in the source package.
The input archive is never modified or copied into the public output.
"""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import argparse, collections, csv, hashlib, io, json, re, tarfile, tempfile, types


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def select(value, keys):
    return {key: value[key] for key in keys if key in value}


def csv_data(rows, fields=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = args.destination / "reproducibility"
    root.mkdir(parents=True, exist_ok=False)
    excluded, projected = [], []

    def put(name, data):
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe output path")
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.encode() if isinstance(data, str) else data)

    with ZipFile(args.source) as z:
        def original(name):
            return z.read("reproducibility/" + name)

        # Keep source and dependency declarations; omit unlicensed/non-code assets.
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename.removeprefix("reproducibility/")
            reason = None
            if name.startswith("app/public/") and Path(name).suffix not in {".json", ".txt"}:
                reason = "Artwork or binary asset: redistribution provenance not established"
            elif name.startswith(("app/patients/", "model/data/patients/")):
                reason = "Original study profile: casebook-derived clinical narratives withheld conservatively"
            elif name.startswith(("model/data/questionnaires/", "model/data/icd11_templates/")):
                reason = "Instrument or clinical classification content: obtain applicable permission separately"
            elif name.startswith("experiments/"):
                reason = "Replaced with explicitly selected numerical projections and public analysis"
            elif not name.startswith(("app/", "model/")) and name != "RUNNING.md":
                reason = "Replaced with public-edition documentation and integrity metadata"
            if reason:
                excluded.append({"source_path": name, "reason": reason, "sha256": sha(z.read(info))})
            else:
                put(name, z.read(info))

        # The archived analysis computes the same endpoints; only its raw-answer
        # availability check is adapted to an explicit boolean projection.
        analysis = original("experiments/_analysis.py").decode()
        old = "require(isinstance(answer.get('answer'),str) and answer['answer'].strip(),'Completed answer is absent')"
        assert analysis.count(old) == 1
        put("experiments/_analysis.py", "# Modified 2026-10-27: numerical projection; raw answers are withheld.\n" + analysis.replace(old, "require(answer.get('answer_present') is True,'Completed-answer availability flag is absent')"))
        put("experiments/scoring.py", original("experiments/scoring.py"))
        put("experiments/expected_results.json", original("experiments/expected_results.json"))
        put("LICENSE", original("model/LICENSE"))

        # Preserve all 30 numeric response vectors; do not distribute item text,
        # licensed keys, normative tables, interpretation text or severity labels.
        def numeric_tree(value):
            if isinstance(value, dict):
                return {k: numeric_tree(v) for k, v in value.items()
                        if isinstance(v, (dict, int, float, bool)) and k not in {"notes"}}
            if type(value) in {int, float, bool}:
                return value
            raise ValueError("Non-numeric leaf")

        for name in z.namelist():
            prefix = "reproducibility/experiments/01_questionnaires/results/"
            if name.startswith(prefix) and name.endswith(".json"):
                value = json.loads(z.read(name))
                value = select(value, ("questionnaire_id", "patient_id", "answers", "scores"))
                value["scores"] = numeric_tree(value["scores"])
                put(name.removeprefix("reproducibility/"), encoded(value))
                projected.append({"source_path": name.removeprefix("reproducibility/"), "source_sha256": sha(z.read(name)), "projection": "Numeric answers and scores; no wording, interpretation or scoring keys"})

        manifest = json.loads(original("experiments/MANIFEST.json"))
        with tarfile.open(fileobj=io.BytesIO(original("experiments/evidence.tar.gz")), mode="r:gz") as tar:
            members = {m.name: m for m in tar.getmembers()}
            def source_bytes(name):
                target = manifest.get("aliases", {}).get(name, {}).get("target", name)
                return tar.extractfile(members[target]).read()

            def project(name, transform, jsonl=False):
                raw = source_bytes(name)
                if jsonl:
                    values = [transform(json.loads(line)) for line in raw.decode().splitlines() if line.strip()]
                    data = b"".join((json.dumps(v, ensure_ascii=False) + "\n").encode() for v in values)
                else:
                    data = encoded(transform(json.loads(raw)))
                put("experiments/evidence/" + name, data)
                projected.append({"source_path": "evidence.tar.gz!/" + name, "source_sha256": sha(raw), "projection_sha256": sha(data), "projection": "Selected numeric/categorical fields only; free text omitted"})

            all_names = set(members) | set(manifest.get("aliases", {}))
            for name in sorted(all_names):
                if re.fullmatch(r"outputs/reviewer-tests-openrouter-2026-09-27/phq/[^/]+/run_\d+/phq9.json", name):
                    project(name, lambda d: {**select(d, ("patient_id", "questionnaire_id", "answers")), "scores": {"total": d["scores"]["total"]}})

            base = "outputs/memory-comparison-run-2026-09-29/"
            project(base + "review/export-001/private/mapping.json", lambda d: {"records": [select(v, ("id", "arm", "answer_available", "application_guard_failure")) for v in d["records"]]})
            def continuity_ratings(d):
                return {"ratings": [{"id": v["id"], "category": v["category"], "fields": {k: {"status": x["status"]} for k, x in v["fields"].items()}} for v in d["ratings"]]}
            for name in ("evaluator_a.json", "evaluator_b.json", "adjudicator.json"):
                project(base + "review/ratings/" + name, continuity_ratings)

            families = ["memory-length-stress-2026-09-30", "openrouter-compression-length-2026-09-30", "regional-memory-compression-2026-09-30", "structured-regional-comparison-2026-10-01", "full-saved-memory-comparison-2026-10-01"]
            for family in families:
                base = "outputs/" + family + "/"
                project(base + "review/private/mapping.json", lambda d: {k: select(v, ("job_id", "patient_id", "arm", "target_tokens")) for k, v in d.items()})
                for name in ("a.json", "b.json", "adjudicator.json"):
                    path = base + "review/ratings/" + name
                    if path in all_names:
                        project(path, lambda d: {"ratings": [{"id": v["id"], "categories": [select(c, ("category", "pass", "field_correct")) for c in v["categories"]]} for v in d["ratings"]]})
                project(base + "schedule.json", lambda d: {"jobs": [select(v, ("job_id", "patient_id", "arm", "target_tokens", "mode", "fact_position", "paired_baseline_job_ids")) for v in d["jobs"]]})
                path = base + "runtime-02/answers.jsonl"
                if path not in all_names:
                    path = base + "runtime/answers.jsonl"
                project(path, lambda d: {**select(d, ("job_id", "patient_id", "arm", "target_tokens", "status")), "answer_present": isinstance(d.get("answer"), str) and bool(d["answer"].strip())}, jsonl=True)

        # Extract only scores and turn labels from workbooks, never the workbooks
        # or the embedded transcript text, author metadata or comments.
        module = types.ModuleType("private_workbook_reader")
        exec(compile(original("experiments/02_missteps/clinician_ratings/recompute.py"), "private_workbook_reader", "exec"), module.__dict__)
        with tempfile.TemporaryDirectory(prefix="llmpatients-numeric-export-") as scratch:
            local = Path(scratch)
            (local / "workbooks").mkdir()
            for rater in module.SOURCE_HASHES:
                name = "workbooks/" + rater + "_completed.xlsx"
                (local / name).write_bytes(original("experiments/02_missteps/clinician_ratings/" + name))
            rows, summaries = module.extract(local)
            put("experiments/02_missteps/clinician_ratings/transcript_ratings.csv", module.csv_bytes(module.LONG_FIELDS, rows))
            put("experiments/02_missteps/clinician_ratings/expected_summary.csv", module.csv_bytes(module.SUMMARY_FIELDS, summaries))
            turn_rows = []
            for rater in module.SOURCE_HASHES:
                sheets = module.workbook_sheets(local / "workbooks" / (rater + "_completed.xlsx"))
                for transcript, cells in sheets.items():
                    for turn in range(1, 16):
                        value = cells.get("E" + str(turn + 15), (None, False))[0]
                        turn_rows.append({"rater_id": rater, "transcript_id": transcript, "turn": turn, "positive": str(value or "").strip().lower() == "yes"})
            put("experiments/02_missteps/turn_labels.csv", csv_data(turn_rows))
        put("experiments/02_missteps/source_workbook_hashes.json", encoded(module.SOURCE_HASHES))
        predictions = json.loads(original("experiments/02_missteps/predictions.json"))
        put("experiments/02_missteps/predictions.json", encoded([{
            "transcriptId": d["transcriptId"], "scriptVariant": d["scriptVariant"],
            "summary": {"therapistTurnCount": d["summary"]["therapistTurnCount"]},
            "detectedCategories": [{"therapistTurns": c.get("therapistTurns", [])} for c in d["detectedCategories"]]
        } for d in predictions]))
        put("experiments/02_missteps/expected_metrics.csv", original("experiments/02_missteps/expected_metrics.csv"))
        legacy = original("experiments/missteps.py").decode()
        begin, end = legacy.index("def labels("), legacy.index("\n\ndef recompute(")
        replacement = '''def labels(path):
    rater = path.name.removesuffix('_completed.xlsx')
    data = path.parent.parent.parent / 'turn_labels.csv'
    rows = [r for r in csv.DictReader(data.open()) if r['rater_id'] == rater]
    out = {(r['transcript_id'], int(r['turn'])): r['positive'] == 'True' for r in rows}
    if len(out) != len(rows) or len(out) != 300:
        raise ValueError('Expected 300 unique projected therapist-turn labels')
    return out
'''
        put("experiments/missteps.py", "# Modified 2026-10-27: read numeric CSV projections instead of withheld XLSX.\n" + legacy[:begin] + replacement + legacy[end:])

    # Completely new demonstration profile, unrelated to any study casebook.
    demo = {"identifiers": {"patientId": "demo_original_001", "externalPatientId": "demo_original_001"},
            "profile": {"name": "Demo Participant", "age": 34, "gender": "other", "smallDescription": "Original fictional example for checking software connections."},
            "chat": {"welcomeMessage": "Hello. I would like to practice explaining my plans for a community garden."},
            "therapy": {"objectives": ["Practice listening and asking clear questions"], "difficulty": 1, "estimatedDuration": 15},
            "clinical": {"clinicalCase": "This fictional adult is planning a community garden and wants to explain a weekly schedule clearly. No diagnosis, treatment or clinical history is assigned.", "details": {"demographicAndSocioculturalInformation": {"age": 34, "gender": "other", "spokenLanguage": "english"}, "educationAndEmployment": {"hobbiesAndInterests": "Planning a community garden."}}}}
    for name in ("app/patients/demo_original_001.yaml", "model/data/patients/demo_original_001.yaml"):
        put(name, encoded(demo))  # JSON is valid YAML and avoids a build dependency.
    put("model/data/questionnaires/README.md", "Questionnaire wording and scoring definitions are intentionally absent. Obtain authorized definitions locally; do not commit them. The generic runner remains in agent/core/questionnaire_runner.py.\n")
    put("model/data/icd11_templates/README.md", "Clinical classification templates are omitted from the public edition. Use original or separately authorized local input.\n")
    put("experiments/EXCLUSIONS.json", encoded({"policy": "Conservative public export: no instrument wording, manuals, scoring keys, normative tables, casebook narratives, original transcripts, artwork, nested archives or private credentials.", "excluded_or_replaced_zip_members": excluded, "selected_projections": projected}))
    put("experiments/run.py", PUBLIC_RUNNER)
    put(".gitignore", ".env\n.env.*\n!.env.example\n__pycache__/\n*.py[cod]\n.venv/\nnode_modules/\n.next/\n.DS_Store\n*.zip\n*.tar\n*.gz\n*.pdf\n*.xlsx\nmodel/data/questionnaires/*\n!model/data/questionnaires/README.md\nmodel/data/icd11_templates/*\n!model/data/icd11_templates/README.md\napp/patients/*\n!app/patients/demo_original_001.yaml\nmodel/data/patients/*\n!model/data/patients/demo_original_001.yaml\n")
    put("README.md", README)
    put("experiments/README.md", EXPERIMENT_README)
    put("THIRD_PARTY_MATERIALS.md", THIRD_PARTY)
    for name in ("app/README.md", "model/README.md", "RUNNING.md"):
        path = root / name
        if path.exists():
            path.write_text("> Public edition (2026-10-27): original study profiles, artwork and licensed questionnaires are withheld. A new non-clinical demo profile is supplied. See the root README and THIRD_PARTY_MATERIALS.md. These archived setup instructions have not been retested as a complete application deployment in this export.\n\n" + path.read_text())
    put("tools/build_public_package.py", Path(__file__).read_bytes())
    put("BUILD_INFO.json", encoded({"edition": "public-numerical-replication-2026-10-27", "source_archive_sha256": sha(args.source.read_bytes()), "source_snapshot": "Anonymized submission archive dated 2026-10-19", "modified": "Public projections, verification entry point, documentation and original demo fixture", "raw_generation_reproducibility": "Requires separately authorized study profiles, instrument definitions and original run artifacts; these are not distributed"}))
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            files[str(path.relative_to(root))] = {"bytes": len(data), "sha256": sha(data)}
    put("MANIFEST.json", encoded({"version": 1, "scope": "Public edition: exact integrity of supplied files; not evidence of access to withheld originals", "files": files}))
    print(json.dumps({"root": str(root), "files": len(files) + 1, "numeric_projections": len(projected)}, indent=2))


PUBLIC_RUNNER = '''"""Verify public files and recompute saved numerical endpoints, offline.

Modified 2026-10-27. Does not reconstruct prompts, rerate responses, validate
licensed scoring keys, or establish semantic correctness of omitted answers.
"""
from pathlib import Path, PurePosixPath
from collections import defaultdict
from decimal import Decimal
import argparse, csv, hashlib, json
import _analysis
from missteps import recompute


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parent
    manifest = json.loads((root / 'MANIFEST.json').read_text())['files']
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()
              and p.name != 'MANIFEST.json' and '__pycache__' not in p.parts
              and '.git' not in p.parts}
    if actual != set(manifest):
        raise ValueError('Unexpected or missing public files')
    for name, expected in manifest.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or (root / name).is_symlink():
            raise ValueError('Unsafe manifest path')
        data = (root / name).read_bytes()
        if {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} != expected:
            raise ValueError('File changed: ' + name)
    reported = _analysis.run(here / 'evidence')
    if reported != json.loads((here / 'expected_results.json').read_text()):
        raise ValueError('Reported numerical endpoints differ')
    panel = recompute(here / '02_missteps')
    ratings_root = here / '02_missteps/clinician_ratings'
    with (ratings_root / 'transcript_ratings.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    keys = {(r['rater_id'], r['transcript_id'], r['dimension_id']) for r in rows}
    if len(rows) != len(keys) or len(rows) != 240:
        raise ValueError('Expected 240 unique clinician ratings')
    groups = defaultdict(list)
    for row in rows:
        score = int(row['score'])
        if not 1 <= score <= 5:
            raise ValueError('Invalid clinician score')
        groups[row['rater_id'], row['dimension_id']].append(score)
    with (ratings_root / 'expected_summary.csv').open() as stream:
        summaries = list(csv.DictReader(stream))
    if len(summaries) != len(groups) or len(groups) != 12:
        raise ValueError('Expected 12 clinician dimension summaries')
    for row in summaries:
        scores = groups[row['rater_id'], row['dimension_id']]
        if len(scores) != 20 or len(scores) != int(row['n']) or Decimal(sum(scores)) / len(scores) != Decimal(row['mean']):
            raise ValueError('Clinician summary differs')
    originals = list((here / '01_questionnaires/results').glob('*/*.json'))
    if len(originals) != 30:
        raise ValueError('Expected 30 numeric original administrations')
    result = {'status': 'PASS', 'network_calls': 0, 'integrity_files': len(manifest),
              'reported_numeric_endpoints_match': True, 'clinician_ratings': 240,
              'clinician_summary_means': 12, 'detector_therapist_turns': 300,
              'original_numeric_administrations_preserved': 30,
              'licensed_questionnaire_rescoring': 'NOT_RUN: definitions and keys withheld',
              'raw_prompt_and_response_validation': 'NOT_RUN: originals withheld',
              'semantic_rerating': 'NOT_RUN', 'application_deployment': 'NOT_TESTED',
              'reported_endpoints': reported, 'missteps': panel}
    if args.output:
        destination = args.output.resolve()
        if destination.is_relative_to(root):
            raise ValueError('Choose an output outside the package')
        with destination.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'reported_endpoints', 'missteps'}}, indent=2))


if __name__ == '__main__':
    run()
'''

README = '''# LLMPatients: public replication package

This is the public numerical-replication edition of the anonymized review
archive, prepared on 27 October 2026. It includes application and runtime source,
dependency declarations, numerical observations and offline analysis code.

## Verify saved numerical results

Use Python 3.10 or later. No third-party Python package, model call or API key is
needed for this command. Clone the repository, enter its root directory and run:

```sh
python3 -B experiments/run.py
```

Optional: save a detailed report to a new path outside the repository:

```sh
python3 -B experiments/run.py --output ../public-replication-results.json
```

The check recalculates repeated PHQ numerical totals, the eleven-session
comparison and five context-policy analyses from selected numerical/categorical
records. It also checks detector metrics for 300 therapist turns, 240 clinician
ratings and 12 dimension means against the archived reference results.

## Scope and limits

This release supports **numerical recomputation of saved observations**. It does
not independently rerate responses, regenerate the original study conversations,
verify raw transmitted prompts, or redistribute the original clinical cases.
Thirty original questionnaire numeric answer vectors and numeric saved scores
are retained, but their licensed scoring definitions and keys are absent, so
rescoring those instruments is explicitly NOT RUN. A PASS applies only to the
public checks listed in the report.

Instrument wording, SCID interviews and manuals, SNAP scoring workbooks,
normative tables, original casebook-derived profiles, raw prompts, response text,
original clinician workbooks and artwork are excluded. The original nested
evidence archive is not distributed. `experiments/EXCLUSIONS.json` records what
was replaced and the source hashes for selected projections.

## Software

`app/` and `model/` retain their existing AGPL-3.0 license texts. Dependency
sources, model weights and third-party media are not bundled. The runtime
snapshot includes affective-state changes made after some archived experiments;
saved-result recomputation does not evaluate those changes.

A completely new, fictional, non-clinical profile (`demo_original_001`) is
included for connection testing. It is not one of the study profiles and cannot
reproduce study generations. Original image files are not supplied, so archived
image references may show missing assets. Full application deployment has not
been retested for this public export. Archived setup procedures are in
`RUNNING.md`, `app/README.md` and `model/README.md`.

Obtain separately authorized instrument definitions and study inputs locally
when needed. Do not commit them or private provider credentials. See
`THIRD_PARTY_MATERIALS.md` for the conservative exclusion policy.

`MANIFEST.json` verifies the supplied files. `BUILD_INFO.json` records the source
archive SHA-256. `tools/build_public_package.py` documents the export process;
rebuilding requires legitimate access to the private source archive. Licenses
and required notices are preserved; this is not a claim that the code is free of
copyright.
'''

EXPERIMENT_README = '''# Public numerical evidence

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
'''

THIRD_PARTY = '''# Third-party materials and distribution scope

This export uses a conservative inclusion policy: existing project source with
its AGPL notices, numerical observations, selected categorical labels, and an
original demonstration fixture. It makes no blanket claim that every instrument
mentioned has the same licensing conditions.

Excluded from this public copy:

- All questionnaire item definitions, item wording, answer-label wording,
  SCID interviews/manuals and instrument PDFs.
- SNAP scoring spreadsheets, scoring keys and normative tables.
- Original clinical study profiles, casebook narrative, original dialogue,
  prompts and model-request/response logs, including compressed nested copies.
- Original clinician XLSX files, including their text and embedded metadata;
  numeric ratings and turn annotations are exported separately.
- Graphics and other binary assets without established redistribution provenance.
- Dependency bundles, model weights, repository history and private credentials.

Rights-holder information consulted on 27 October 2026:

- [University of Minnesota Press test permissions](https://www.upress.umn.edu/test-division/permissions-and-ordering/): describes restrictions on online reproduction of test items and contact information for SNAP-2 use.
- [American Psychiatric Association Publishing permissions](https://www.appi.org/Support/Customer-Information/Permissions): obtain applicable instrument/content permissions from the rights holder.
- [GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html): source license texts are retained unchanged in the root, `app/` and `model/`.

Obtain required materials through authorized channels and keep them outside
public source control. Existing software licenses are not permission to
redistribute third-party tests, book content or images.
'''


if __name__ == "__main__":
    main()
