# Automotive RAG

This repo is for building a production-minded RAG system that answers vehicle troubleshooting and maintenance questions from manufacturer documentation.

The manuals currently live in [manuals](/Users/konark/Desktop/Personal/automotive-rag/manuals). The long-term goal is to support many manuals across makes, models, and years while keeping the system grounded, explainable, and production-friendly.

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

- [docs/ingestion.md](/Users/konark/Desktop/Personal/automotive-rag/docs/ingestion.md)
- [docs/chunking.md](/Users/konark/Desktop/Personal/automotive-rag/docs/chunking.md)

### Part 2: Sample QA And Evaluation

Focus:

- define what a good answer looks like
- create a small evaluation set
- decide how retrieval and final answers will be measured

Key document:

- [docs/evaluation.md](/Users/konark/Desktop/Personal/automotive-rag/docs/evaluation.md)

### Part 3: Retrieval And Answer Generation

Focus:

- implement hybrid retrieval
- add reranking
- answer using only grounded manufacturer evidence
- compare basic hybrid and hierarchical hybrid later

Key documents:

- [docs/architecture.md](/Users/konark/Desktop/Personal/automotive-rag/docs/architecture.md)
- [docs/datastore.md](/Users/konark/Desktop/Personal/automotive-rag/docs/datastore.md)

## Project Docs

- [docs/architecture.md](/Users/konark/Desktop/Personal/automotive-rag/docs/architecture.md): top-level architecture choices
- [docs/dev-notes.md](/Users/konark/Desktop/Personal/automotive-rag/docs/dev-notes.md): local rerun commands for setup, chunk generation, inspection, and checks
- [docs/ingestion.md](/Users/konark/Desktop/Personal/automotive-rag/docs/ingestion.md): extraction, metadata, tables, images, TOC, and ingestion quality checks
- [docs/chunking.md](/Users/konark/Desktop/Personal/automotive-rag/docs/chunking.md): chunking strategy options and the recommended approach
- [docs/datastore.md](/Users/konark/Desktop/Personal/automotive-rag/docs/datastore.md): storage options for vector and keyword search
- [docs/evaluation.md](/Users/konark/Desktop/Personal/automotive-rag/docs/evaluation.md): answer quality and evaluation methodology

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
