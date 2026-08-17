# Datastore

This document records the storage and indexing choices for the retrieval layer.

## Goal

Choose a datastore approach that supports:

- dense vector search
- keyword search
- metadata filtering
- reranking inputs
- future hierarchical retrieval
- production-friendly operations without unnecessary early complexity

## Options

### Option 1: PostgreSQL + pgvector + PostgreSQL Full-Text Search

Strengths:

- one system for structured metadata, vectors, and keyword search
- relational model fits documents, sections, chunks, and lineage well
- easy metadata filtering and joins
- strong debugging story
- good fit for portfolio work and production-minded learning

Tradeoffs:

- not the most search-specialized option at very large scale
- hybrid scoring may require more application-side fusion logic
- search tuning is less turnkey than dedicated search engines

### Option 2: Qdrant + sparse and dense vectors

Strengths:

- built for vector retrieval
- supports dense and sparse vectors in one point
- supports hybrid and multi-stage queries
- good fit for advanced retrieval experiments

Tradeoffs:

- less natural than Postgres for relational ingestion metadata
- some non-search application data will likely still want a second store
- adds more system design choices earlier

### Option 3: OpenSearch

Strengths:

- search-native system
- strong lexical search foundations
- supports vector and hybrid search
- powerful when search is the central platform concern

Tradeoffs:

- heavier operational footprint
- more infrastructure than this project needs right now
- less friendly as a first production-minded learning path

### Option 4: Weaviate

Strengths:

- built-in hybrid search
- supports BM25 and vector fusion
- convenient for rapid experimentation

Tradeoffs:

- more framework-like abstraction than we need initially
- less transparent for learning the mechanics than a simpler stack
- still another service with its own operating model

## Recommendation

Recommendation: `PostgreSQL + pgvector + PostgreSQL full-text search`.

Why this is the best fit now:

- it supports both vector and keyword retrieval in one datastore
- it matches the structured nature of manuals and metadata
- it keeps the system easier to inspect, explain, and evolve
- it leaves room for hierarchical metadata without redesigning the data model

For this repo, the best first tradeoff is not the most specialized retrieval engine. It is the one that gives strong retrieval, clean metadata modeling, and easy observability in one place.

## Decision Details

### 1. Should vector and keyword search live in one datastore?

Recommendation: `Yes`, for v1.

Why:

- simpler ingestion and indexing pipeline
- easier joins between chunk records and metadata
- easier debugging of retrieval failures
- lower operational complexity

### 2. Should we keep the schema hierarchical?

Recommendation: `Yes`.

Suggested logical entities:

- `documents`
- `sections`
- `chunks`
- `tables`
- `ingestion_runs`

This shape keeps basic hybrid RAG easy while preserving a path to hierarchical retrieval later.

### 3. How should hybrid retrieval be composed?

Recommendation: keep retrieval composition in the application layer.

Suggested pattern:

- run dense retrieval
- run keyword retrieval
- fuse candidates
- apply reranking

Why:

- easier to compare strategies
- easier to log intermediate rankings
- easier to swap fusion logic later

### 4. What should keyword search index?

Recommendation:

- chunk text
- section titles
- heading path
- table text renderings
- selected metadata fields where useful

This helps exact matches like warning labels, maintenance terms, fluid names, and part terminology.

### 5. What should vector search embed?

Recommendation:

- primary chunk text
- optionally section summaries later
- table text renderings when they contain question-answerable content

Do not embed everything blindly. Preserve control over what becomes semantically searchable.

### 6. When should we consider another datastore later?

Revisit the choice if:

- corpus size grows enough to make search latency hard to manage
- hybrid ranking control becomes too limited
- we want search-native features beyond what Postgres gives comfortably
- we move into more advanced multi-stage or multimodal retrieval

If that happens, the most likely next candidates are:

- `Qdrant` for vector-first and multi-stage retrieval experiments
- `OpenSearch` for search-heavy production scale

## Chosen Path

The recommended datastore path is:

1. Use PostgreSQL as the system of record.
2. Use `pgvector` for dense embeddings.
3. Use PostgreSQL full-text search for keyword retrieval.
4. Keep hybrid fusion and reranking logic in the application layer.
5. Model data so sections and chunks preserve hierarchy and provenance.

## References

- PostgreSQL full-text search overview: <https://www.postgresql.org/docs/18/textsearch.html>
- PostgreSQL text search types: <https://www.postgresql.org/docs/18/datatype-textsearch.html>
- PostgreSQL text search functions and operators: <https://www.postgresql.org/docs/18/functions-textsearch.html>
- pgvector README: <https://github.com/pgvector/pgvector/blob/master/README.md?plain=1>
- Qdrant hybrid search: <https://qdrant.tech/documentation/search/text-search/hybrid-search/>
- Qdrant hybrid and multi-stage queries: <https://qdrant.tech/documentation/search/hybrid-queries/>
- OpenSearch hybrid search tutorial: <https://docs.opensearch.org/latest/tutorials/vector-search/neural-search-tutorial/>
- Weaviate hybrid search: <https://docs.weaviate.io/weaviate/concepts/search/hybrid-search>
