# Dev Notes

This document records the main local commands for rerunning the current ingestion, chunking, embedding, and local database workflow.

## Environment Setup

Create the virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

## Local Postgres

The Docker setup reads credentials from `.env`:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `PGADMIN_DEFAULT_EMAIL`
- `PGADMIN_DEFAULT_PASSWORD`
- `PGADMIN_PORT`

Start the local PostgreSQL + `pgvector` + `pgAdmin` containers:

```bash
docker compose up -d
```

Stop the container:

```bash
docker compose down
```

Stop the container and remove the database volume:

```bash
docker compose down -v
```

View database logs:

```bash
docker compose logs -f postgres
```

View `pgAdmin` logs:

```bash
docker compose logs -f pgadmin
```

Open `pgAdmin` in the browser:

```text
http://localhost:${PGADMIN_PORT:-5050}
```

Login with:

- email: `PGADMIN_DEFAULT_EMAIL`
- password: `PGADMIN_DEFAULT_PASSWORD`

In `pgAdmin`, register the local Postgres server with:

- host: `postgres`
- port: `5432`
- database: `POSTGRES_DB`
- username: `POSTGRES_USER`
- password: `POSTGRES_PASSWORD`

Connect with `psql` inside the container:

```bash
set -a
source .env
set +a
docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-automotive_rag}"
```

Check that `pgvector` is enabled:

```bash
set -a
source .env
set +a
docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-automotive_rag}" -c "\\dx"
```

The local defaults in [docker-compose.yml](/Users/konark/Desktop/Personal/automotive-rag/docker-compose.yml) are:

- database: `automotive_rag`
- user: read from `POSTGRES_USER`
- password: read from `POSTGRES_PASSWORD`
- postgres port: `5432`
- pgAdmin port: `5050`

You can override the database values with `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_PORT`, and the `pgAdmin` login and port with `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`, and `PGADMIN_PORT`.

## Chunk Generation

Run chunk generation for all manuals:

```bash
.venv/bin/python scripts/create_chunks.py
```

Run chunk generation for a single manual:

```bash
.venv/bin/python scripts/create_chunks.py --match 'filename'
```

Example:

```bash
.venv/bin/python scripts/create_chunks.py --match '2026-toyota-corolla.pdf'
```

Tune chunk sizing:

```bash
.venv/bin/python scripts/create_chunks.py \
  --target-tokens 450 \
  --soft-max-tokens 650 \
  --hard-max-tokens 800
```

## Artifacts

Generated files go to:

- `artifacts/documents`: raw structured Docling document JSON
- `artifacts/chunks`: final chunk artifacts
- `artifacts/reports`: per-manual reports and aggregate summary

Embedding artifacts go to:

- `artifacts/embeddings`: one JSONL file per manual with chunk vectors
- `artifacts/embedding-reports`: per-manual embedding reports and aggregate summary

Database init files live in:

- `db/init`: SQL files run automatically on first container startup

Apply the schema manually to an existing local container:

```bash
set -a
source .env
set +a
docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d "${POSTGRES_DB:-automotive_rag}" \
  -f /docker-entrypoint-initdb.d/002-create-schema.sql
```

## Embeddings

Generate embeddings for all chunk files:

```bash
.venv/bin/python scripts/create_embeddings.py
```

Generate embeddings for a single manual:

```bash
.venv/bin/python scripts/create_embeddings.py --match '2020-toyota-yaris.json'
```

Regenerate embeddings if output files already exist:

```bash
.venv/bin/python scripts/create_embeddings.py --overwrite
```

Tune batching:

```bash
.venv/bin/python scripts/create_embeddings.py --batch-size 32
```

## PostgreSQL Load

Load all chunk and embedding artifacts into PostgreSQL:

```bash
.venv/bin/python scripts/load_postgres.py
```

Load one document:

```bash
.venv/bin/python scripts/load_postgres.py --match '2020-toyota-yaris.json'
```

If the schema is already applied and you only want to reload data:

```bash
.venv/bin/python scripts/load_postgres.py --skip-schema
```

Inspect the summary report:

```bash
sed -n '1,240p' artifacts/reports/summary.json
```

Inspect one chunk artifact:

```bash
sed -n '1,200p' artifacts/chunks/2020-toyota-yaris.json
```

Inspect one embedding artifact:

```bash
sed -n '1,5p' artifacts/embeddings/2020-toyota-yaris.jsonl
```

Print a compact report summary:

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/reports/summary.json").read_text())
print("manual_count:", summary["manual_count"])
for report in summary["reports"]:
    print(
        report["doc_id"],
        "pages=", report["page_count"],
        "sections=", report["section_count"],
        "chunks=", report["chunk_count"],
        "avg_chunk_tokens=", report["avg_chunk_tokens"],
        "max_chunk_tokens=", report["max_chunk_tokens"],
    )
PY
```
