"""Verify public files and recompute saved numerical endpoints, offline.

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
            stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'reported_endpoints', 'missteps'}}, indent=2))


if __name__ == '__main__':
    run()
