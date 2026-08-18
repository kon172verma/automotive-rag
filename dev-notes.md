# Dev Notes

This document records the main local commands for rerunning the current ingestion and chunking workflow.

## Environment Setup

Create the virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

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

Inspect the summary report:

```bash
sed -n '1,240p' artifacts/reports/summary.json
```

Inspect one chunk artifact:

```bash
sed -n '1,200p' artifacts/chunks/2020-toyota-yaris.json
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
