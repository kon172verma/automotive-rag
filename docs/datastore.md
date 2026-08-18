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

What `pgvector` is in this option:

- a PostgreSQL extension that adds vector column types and vector similarity operators
- supports exact search by default and approximate nearest neighbor indexing with `HNSW` and `IVFFlat`
- lets us keep embeddings, relational metadata, and keyword search in the same database

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

### Option 5: Pinecone

Strengths:

- fully managed service with strong vector search ergonomics
- supports integrated embeddings and hosted reranking
- supports dense, sparse, and full-text-style ranking fields in newer document-oriented indexing flows
- good fit if we want managed infrastructure and faster hosted experimentation

Tradeoffs:

- less transparent than Postgres for relational metadata modeling and joins
- some richer document-style indexing capabilities are newer and should be adopted carefully
- less educational than an explicit app-managed retrieval pipeline if learning internals is a priority

### Option 6: Chroma

Strengths:

- simple developer experience
- good for local prototyping and quick iteration
- supports embedding functions, sparse embeddings, and hybrid ranking expressions
- easy to use when we want to test retrieval ideas quickly

Tradeoffs:

- less natural than Postgres for rich hierarchy, ingestion bookkeeping, and relational queries
- better suited to experimentation than to our preferred production-minded default
- reranking is more naturally handled in the application layer than treated as a core integrated database feature

## Recommendation

Recommendation: `PostgreSQL + pgvector + PostgreSQL full-text search`.

Why this is the best fit now:

- it supports both vector and keyword retrieval in one datastore
- it matches the structured nature of manuals and metadata
- it keeps the system easier to inspect, explain, and evolve
- it leaves room for hierarchical metadata without redesigning the data model

For this repo, the best first tradeoff is not the most specialized retrieval engine. It is the one that gives strong retrieval, clean metadata modeling, and easy observability in one place.

Practical note:

- `Weaviate/Chroma` are reasonable if we want faster experimentation with more built-in abstractions
- `Pinecone` is a strong managed option if we want more hosted retrieval components with less infrastructure work
- `PostgreSQL + pgvector` still remains the clearest default for this repo because of metadata modeling, inspectability, and learning value
- for local development, we will run PostgreSQL in Docker using the `pgvector/pgvector` image so the extension is available immediately

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

- an `embedding_text` field built from primary chunk text plus selected heading context
- optionally section summaries later
- table text renderings when they contain question-answerable content

Do not embed the full metadata blob blindly. Preserve control over what becomes semantically searchable.

### 5A. How should chunks be stored?

Recommendation: use relational rows as the primary storage format.

Suggested chunk record shape:

- structured columns for ids, page spans, hierarchy, and searchable text
- one vector column for embeddings
- optional `jsonb` column for raw extractor output or extended attributes

This gives us:

- fast metadata filters
- easy debugging of hierarchy and sibling relationships
- room for raw structured payloads without making JSON the only source of truth

### 6. When should we consider another datastore later?

Revisit the choice if:

- corpus size grows enough to make search latency hard to manage
- hybrid ranking control becomes too limited
- we want search-native features beyond what Postgres gives comfortably
- we move into more advanced multi-stage or multimodal retrieval

If that happens, the most likely next candidates are:

- `Qdrant` for vector-first and multi-stage retrieval experiments
- `OpenSearch` for search-heavy production scale
- `Pinecone` for a more managed hosted retrieval stack
- `Weaviate/Chroma` for faster experimentation with more built-in retrieval abstractions

## Chosen Path

The recommended datastore path is:

1. Use PostgreSQL as the system of record.
2. Use `pgvector` for dense embeddings.
3. Use PostgreSQL full-text search for keyword retrieval.
4. Keep hybrid fusion and reranking logic in the application layer.
5. Model data so sections and chunks preserve hierarchy and provenance.
6. Run the first local development setup in Docker before considering cloud hosting.

## References

- PostgreSQL full-text search overview: <https://www.postgresql.org/docs/18/textsearch.html>
- PostgreSQL text search types: <https://www.postgresql.org/docs/18/datatype-textsearch.html>
- PostgreSQL text search functions and operators: <https://www.postgresql.org/docs/18/functions-textsearch.html>
- pgvector README: <https://github.com/pgvector/pgvector/blob/master/README.md?plain=1>
- Qdrant hybrid search: <https://qdrant.tech/documentation/search/text-search/hybrid-search/>
- Qdrant hybrid and multi-stage queries: <https://qdrant.tech/documentation/search/hybrid-queries/>
- OpenSearch hybrid search tutorial: <https://docs.opensearch.org/latest/tutorials/vector-search/neural-search-tutorial/>
- Weaviate hybrid search: <https://docs.weaviate.io/weaviate/concepts/search/hybrid-search>
- Pinecone index creation and integrated embedding: <https://docs.pinecone.io/guides/index-data/create-an-index>
- Pinecone reranking: <https://docs.pinecone.io/guides/search/rerank-results>
- Chroma embedding functions: <https://docs.trychroma.com/docs/embeddings/embedding-functions>
- Chroma ranking and hybrid search: <https://docs.trychroma.com/cloud/search-api/ranking>
