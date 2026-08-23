# Automotive RAG

This repo is for building a production-minded RAG system that answers vehicle troubleshooting and maintenance questions from manufacturer documentation.

The manuals currently live in [manuals](./manuals/). The long-term goal is to support many manuals across makes, models, and years while keeping the system grounded, explainable, and production-friendly.

## Goal

Build a system that:

- takes a user question plus vehicle context
- retrieves the most relevant manual content for that vehicle
- combines keyword and vector retrieval
- reranks retrieved evidence
- gives grounded context to an LLM
- returns a useful answer with citations

This is also a learning project. The goal is to understand RAG deeply while building something portfolio-worthy and production-minded.

## Current Direction

We are not starting with a minimal retrieval baseline.

We will treat `hybrid RAG` as the first baseline:

- keyword search + dense vector search
- metadata-aware filtering
- reranking before generation
- cited answers with page-aware references

Later, we will compare:

- basic hybrid RAG
- hierarchical hybrid RAG

We are finalizing the docs and decision files before making code changes.

## Project Parts

### Part 1: Data Ingestion

Focus:

- extract clean, structured data from manuals
- preserve sections, pages, tables, and metadata
- build chunking and storage decisions that support hybrid RAG now and hierarchical retrieval later

Key document:

- [docs/ingestion.md](./docs/ingestion.md)
- [docs/chunking.md](./docs/chunking.md)

### Part 2: Sample QA And Evaluation

Focus:

- define what a good answer looks like
- create a small evaluation set
- decide how retrieval and final answers will be measured

Key document:

- [docs/evaluation.md](./docs/evaluation.md)
- [docs/evaluation-dataset.md](./docs/evaluation-dataset.md)

### Part 3: Retrieval And Answer Generation

Focus:

- implement hybrid retrieval
- add reranking
- answer using only grounded manufacturer evidence
- compare basic hybrid and hierarchical hybrid later

Key documents:

- [docs/architecture.md](./docs/architecture.md)
- [docs/datastore.md](./docs/datastore.md)
- [docs/retrieval.md](./docs/retrieval.md)
- [docs/generation.md](./docs/generation.md)
- [docs/reranking.md](./docs/reranking.md)
- [docs/retrieval-evaluation.md](./docs/retrieval-evaluation.md)

## Project Docs

- [docs/architecture.md](./docs/architecture.md): top-level architecture choices
- [dev-notes.md](./dev-notes.md): local rerun commands for setup, chunk generation, embeddings, and local database workflow
- [docs/embeddings.md](./docs/embeddings.md): embedding model choices, dimensions, and current recommendation
- [docs/ingestion.md](./docs/ingestion.md): extraction, metadata, tables, images, TOC, and ingestion quality checks
- [docs/chunking.md](./docs/chunking.md): chunking strategy options and the recommended approach
- [docs/datastore.md](./docs/datastore.md): storage options for vector and keyword search
- [docs/evaluation.md](./docs/evaluation.md): answer quality and evaluation methodology
- [docs/evaluation-dataset.md](./docs/evaluation-dataset.md): eval dataset shape, schema, and gold-label conventions
- [docs/retrieval.md](./docs/retrieval.md): hybrid retrieval baseline, filtering, fusion, and retrieval outputs
- [docs/generation.md](./docs/generation.md): grounded answer-generation plan, output schema, and model options
- [docs/reranking.md](./docs/reranking.md): reranking role, candidate pool, and evaluation expectations
- [docs/retrieval-evaluation.md](./docs/retrieval-evaluation.md): retrieval-only metrics and experiment structure

## Source Layout

The codebase is organized under `src/` with Python package names that use underscores:

- `src/chunking`: Docling conversion and chunk artifact creation
- `src/ingestion`: embedding generation and PostgreSQL loading
- `src/fusion`: fusion strategies such as reciprocal-rank fusion
- `src/keyword_retrieval`: lexical retrieval helpers
- `src/vector_retrieval`: dense retrieval and retrieval CLI orchestration
- `src/reranking`: reranker scoring, host service, and service client
- `src/generation`: answer-context packaging and the future answer-generation layer
- `src/evaluation`: retrieval evaluation and future answer evaluation

We are also keeping a simple file-size guideline for Python modules:

- soft limit: about `250` lines
- hard limit: about `350` lines

The goal is to split by responsibility without turning each feature into a pile of tiny files.

## Principles

- keep every answer grounded in manufacturer documentation
- treat vehicle identity as a first-class retrieval signal
- optimize for observability and evaluation, not just demos
- preserve enough structure now so we can test hierarchical retrieval later without redesigning everything
- defer complexity that does not clearly improve retrieval quality

## Not Starting With

Not in the first implementation:

- GraphRAG
- agentic workflows
- web search augmentation
- broad automotive knowledge outside manufacturer manuals

Those may become useful later, but they are not the right starting point for this repo.
