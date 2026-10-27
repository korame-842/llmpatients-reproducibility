# LLMPatients: public replication package

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
