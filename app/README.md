> Public edition (2026-10-27): original study profiles, artwork and licensed questionnaires are withheld. A new non-clinical demo profile is supplied. See the root README and THIRD_PARTY_MATERIALS.md. These archived setup instructions have not been retested as a complete application deployment in this export.

# Application

The web application requires Node.js 22, pnpm 10.12.4 and PostgreSQL 18.
Dependencies are pinned in `pnpm-lock.yaml`; the AGPL source license is in `LICENSE`.

## Docker demo

```sh
API=local docker compose up --build
```

Open **http://localhost:18080**. Compose initializes its own database and demo
accounts: `admin@example.com` and `user@example.com`, password `Qwerty123!`.
Stop with `docker compose down`; the database volume is retained.

## Run from source

```sh
corepack enable
corepack prepare pnpm@10.12.4 --activate
pnpm install --frozen-lockfile
cp -n .env.example .env
docker compose up -d postgres
pnpm db:migrate
pnpm db:seed
PORT=18080 pnpm dev
```

Use a dedicated demo database. Patient replies are simulated with `API=local`;
AI step analysis needs a configured model. Audio is disabled.

## Connect the patient runtime

Follow [Run the complete system](../RUNNING.md) to start the Python API and
connect this application with `API=remote`. The guide also explains the Docker
host-gateway configuration and the separate Vertex AI credentials required for
automated step analysis. `docker-compose.vertex.yml` supplies that optional
detector configuration for the containerized frontend.

## Checks

```sh
pnpm check
pnpm test
TEST_POSTGRES_ADMIN_URL=postgresql://postgres:reviewer-demo-password@127.0.0.1:16543/postgres pnpm test:backend:local
pnpm build
PORT=18080 pnpm start
```

`pnpm test` uses mocked HTTP. The backend check creates and removes an isolated
test database, without AI calls. The first build may download the Inter font.
For the Python backend, see [model](../model/README.md).
