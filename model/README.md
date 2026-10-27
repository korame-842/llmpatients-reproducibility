> Public edition (2026-10-27): original study profiles, artwork and licensed questionnaires are withheld. A new non-clinical demo profile is supplied. See the root README and THIRD_PARTY_MATERIALS.md. These archived setup instructions have not been retested as a complete application deployment in this export.

# Patient runtime

Python 3.12. Includes ten profiles, questionnaire definitions and API/graph tests.
Model weights and credentials are not included; see `LICENSE` for source terms.

## Offline tests

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r agent/requirements-test-lock.txt
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  LANGCHAIN_TRACING=false LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false \
  python -m unittest discover -s agent -t . -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_*.py' -v
```

The 118 tests use synthetic model/encoder fixtures and make no inference calls.

## Optional API

Requires an installed Ollama model and cached MiniLM encoder. Set `model_id`
in `.env` to your local model tag:

```sh
python -m pip install -r agent/requirements-runtime.txt
cp -n .env.example .env
python -m uvicorn agent.api.app:app --host 127.0.0.1 --port 8000
```

The runtime and offline checker share `agent/core/encoder.py`, which loads
`sentence-transformers/all-MiniLM-L6-v2` at revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. There is no fallback to a different
revision. On a connected machine, populate the Hugging Face cache used by this
runtime and check it offline:

```sh
python -c "from agent.core.encoder import load_encoder; load_encoder(device='cpu')"
python scripts/check_encoder.py
```

For offline startup, use the same cache and set `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`. The checker uses `local_files_only=True` and rejects a
missing cache revision. This binding applies to the current runtime; the frozen
experiment sources retain their recorded configurations. An immutable encoder
revision was not recorded for the historical [B] comparison.

For the complete startup procedure, provider configuration and frontend
connection, see [Run the complete system](../RUNNING.md).
The app demo and [saved-result checks](../experiments/README.md) do not need this API.

## Affective-state handling

The runtime preserves the previous affective vector, blends the classifier
target afterwards at weight 0.15, initializes profiles from their trait baselines
and isolates mutable state between conversations. Offline regression checks are
in `agent.test_session_memory.TestEmotionalStateUpdate`.

The experiment sources preserve the implementation used for the reported
results. Saved-result recomputation does not evaluate the current runtime.
The software components are identified separately in `../VERSIONS.json`.
