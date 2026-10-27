> Public edition (2026-10-27): original study profiles, artwork and licensed questionnaires are withheld. A new non-clinical demo profile is supplied. See the root README and THIRD_PARTY_MATERIALS.md. These archived setup instructions have not been retested as a complete application deployment in this export.

# Run the complete system

The web application in `app/` and the patient-generation API in `model/` run as
separate processes. This procedure connects both components. The
[Docker demo](app/README.md#docker-demo) uses simulated replies instead.

Requirements: Python 3.12, Node.js 22, pnpm 10.12.4, Docker for PostgreSQL, an
accessible patient-generation model and the pinned MiniLM encoder. Dependencies
and encoder weights require an initial download. Provider credentials and LLM
weights are configured separately; they are not included in this archive.
Keep credential files outside the extracted package and reference them by their
absolute host paths.

## 1. Configure and start the patient API

From `model/`:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r agent/requirements-runtime.txt
cp -n .env.example .env
```

The default example uses Ollama. Start your Ollama service, use `ollama list` to
identify an installed model, and set `model_id` in `.env` to its exact tag. If the
model is not installed, download it with `ollama pull MODEL_TAG`, replacing
`MODEL_TAG` with the model you intend to use. `ollama_base_url` must point to the
running service.

To use Vertex AI instead, replace the provider and model settings in `model/.env`
and add your project, region and credential-file path:

```dotenv
model_provider=vertex_ai
model_id=YOUR_ACCESSIBLE_VERTEX_MODEL
GCP_PROJECT=YOUR_PROJECT_ID
GCP_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your/credentials.json
```

Use a project and credentials authorized to invoke the selected model. The
patient runtime reads `GCP_PROJECT` and `GCP_LOCATION`; the separate detector
configuration below uses `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`.

Populate and check the exact encoder revision, then start the API:

```sh
HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 \
  python -c "from agent.core.encoder import load_encoder; load_encoder(device='cpu')"
python scripts/check_encoder.py
python -m uvicorn agent.api.app:app --host 127.0.0.1 --port 8000
```

Keep this terminal open. The API schema is available at
**http://127.0.0.1:8000/docs**. The runtime creates its memory and run-log
directories when needed.

## 2. Connect the web application

In a second terminal, from `app/`:

```sh
corepack enable
corepack prepare pnpm@10.12.4 --activate
pnpm install --frozen-lockfile
cp -n .env.example .env
docker compose up -d postgres
pnpm db:migrate
pnpm db:seed
API=remote API_BASE_URL=http://127.0.0.1:8000 \
  API_INITIALIZE_PATIENT_ENDPOINT=/patients PORT=18080 pnpm dev
```

Open **http://localhost:18080** and sign in with `admin@example.com` or
`user@example.com`, password `Qwerty123!`. Start a patient session and send a
message. Requests now use the Python runtime's `/patients`, `/chat-response` and
`/session-end` endpoints. Both processes must remain running.

### Run the web application in Docker instead

Complete the patient-API setup above, but start Uvicorn with
`--host 0.0.0.0 --port 8000` so that the Docker container can reach it through the
host gateway. Then, from `app/`:

```sh
API=remote API_BASE_URL=http://host.docker.internal:8000 docker compose up --build
```

The Compose file supplies the `host.docker.internal` gateway mapping, including
on Linux. A backend bound only to host loopback is not reachable through that
gateway. The native Node procedure above keeps the API on `127.0.0.1`.

## 3. Optional automated step analysis

The misstep detector uses Vertex AI independently of the patient-generation
provider. Ollama patient generation does not configure the detector. For a
native Node frontend, add these settings to `app/.env`:

```dotenv
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
VERTEX_MODEL_ID=YOUR_ACCESSIBLE_DETECTOR_MODEL
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your/credentials.json
```

Restart the frontend after changing its environment. The credential file must
authorize the selected detector model. For a Docker frontend, use the same host
settings and the supplied overlay, which mounts the credential file read-only:

```sh
API=remote API_BASE_URL=http://host.docker.internal:8000 \
  docker compose -f docker-compose.yml -f docker-compose.vertex.yml up --build
```

The credentials remain outside the archive and container image. Without detector
configuration, the application and patient chat can run; automated step analysis
requires that configuration. Audio is disabled in the supplied setup.

## Stop the system

Stop the host processes with Ctrl-C. From `app/`, run `docker compose down` to
stop the demo database and any Compose frontend; the database volume is retained.
If using the detector overlay, pass the same two `-f` arguments when stopping.
Stop Ollama separately if you started it for this run.
