# Architecture

This document captures the top-level architecture choices for the project.

## Project Shape

We will divide the project into three parts:

1. Data ingestion
2. Sample QA and evaluation
3. Document retrieval and answer generation

We will finalize these docs before making implementation changes.

Current `src/` layout:

- `src/chunking`: manual parsing and chunk creation
- `src/ingestion`: embeddings and PostgreSQL loading
- `src/fusion`: fusion strategies such as reciprocal-rank fusion
- `src/keyword_retrieval`: keyword retrieval helpers
- `src/vector_retrieval`: dense retrieval and retrieval orchestration
- `src/reranking`: reranker scoring, service client, and host service
- `src/generation`: answer-context packaging and future answer generation
- `src/evaluation`: retrieval evaluation and future answer evaluation

Implementation guideline:

- keep Python modules near a `250` line soft limit
- avoid going past a `350` line hard limit
- split by responsibility, not by forcing one or two functions per file

## Recommended Starting Point

Start directly with a hybrid RAG system and treat that as the baseline.

Recommended baseline:

- metadata-aware retrieval by make, model, year, and source document
- hybrid retrieval: keyword + dense vector
- reranking before answer generation
- grounded answer generation with citations

This is a better starting point than a simpler dense-only or keyword-only baseline because automotive manuals contain both exact terminology and semantically phrased instructions.

## Key Questions

### 1. Should this be GraphRAG?

Recommendation: `No` for now.

Why:

- manuals are document-heavy, not graph-native
- GraphRAG adds extraction, schema, and debugging overhead
- it is not the best first system for learning practical RAG

Revisit only if later we need cross-document reasoning over parts, systems, dependencies, or repair workflows.

### 2. Should this be Agentic RAG?

Recommendation: `No` for now.

Why:

- the main challenge here is high-quality retrieval
- agent loops add latency and complexity
- they can mask weak retrieval instead of improving it

Revisit only after the core retrieval pipeline is strong and measurable.

### 3. Should hierarchical hybrid RAG be part of the plan?

Recommendation: `Yes`, but not as the first implemented pipeline.

Why:

- manuals often have strong section structure
- hierarchical retrieval may improve precision on long sections
- it is a meaningful comparison candidate for this domain

The plan should be:

1. Build basic hybrid RAG first.
2. Build hierarchical hybrid RAG next.
3. Compare them on the same evaluation set.

### 4. Should reranking be included from the start?

Recommendation: `Yes`.

Why:

- manuals often produce many partially relevant chunks
- reranking is one of the highest-leverage retrieval improvements
- it will make comparisons between retrieval strategies more meaningful

### 5. Should citations be mandatory?

Recommendation: `Yes`.

Why:

- this is a trust-sensitive domain
- users should be able to inspect the grounding evidence
- citations make debugging and evaluation much easier

### 6. Should we use a framework like LlamaIndex or LangChain?

Recommendation: `Not in the core v1 pipeline`.

Why:

- the main project value is custom ingestion, chunking, metadata, and retrieval behavior
- frameworks can reduce boilerplate, but they can also hide retrieval failures
- we want the first version to stay easy to inspect and debug

Current position:

- keep ingestion, chunking, retrieval fusion, and reranking mostly custom
- consider `LlamaIndex` later for evaluation helpers or retrieval experiments
- use `LangChain` only later if we need broader app orchestration

### 7. What embedding model should we choose?

Recommendation: start with `text-embedding-3-small`.

Why:

- it is a strong default embedding model with lower cost and easier iteration than larger options
- it fits the current project stage, where we want to tune chunking, metadata, and retrieval behavior quickly
- it keeps the first working system simple while still giving us a credible production-style path

What to consider alongside it:

- `text-embedding-3-large`: the stronger quality-focused upgrade path if later evaluation shows the need
- `BAAI/bge-m3`: the main open-model alternative if we later want self-hosting or unified dense/sparse retrieval experiments

Why not start with `BAAI/bge-m3`:

- it is powerful, but it adds hosting and operational complexity
- we already plan to do hybrid retrieval using keyword search plus dense vectors, so we do not need unified sparse+dense modeling on day one
- it is better as a later comparison option than the first default

See also: [docs/embeddings.md](./embeddings.md)

## Chosen Path

The recommended path for this repo is:

1. Design the ingestion format so it supports both basic hybrid and hierarchical hybrid later.
2. Build a sample evaluation set early.
3. Build and measure the retrieval-only hybrid baseline first.
4. Add reranking and compare before vs after.
5. Add answer-context packaging before full answer generation.
6. Add answer generation only after retrieval is measurable.
7. Add hierarchical hybrid retrieval as the first major comparison.
8. Keep advanced patterns deferred unless the data proves they help.

## Next Implementation Order

The next implementation phase should be:

1. retrieval-only hybrid baseline
2. retrieval evaluation against the curated eval set
3. reranking comparison
4. grounded answer generation later

See also:

- [docs/retrieval.md](./retrieval.md)
- [docs/reranking.md](./reranking.md)
- [docs/retrieval-evaluation.md](./retrieval-evaluation.md)
- [docs/evaluation-dataset.md](./evaluation-dataset.md)

## What We Are Deferring

Defer these until the basics are working well:

- GraphRAG
- agentic workflows
- multi-hop reasoning across many manuals
- web search augmentation
- broad non-manufacturer automotive knowledge

## Rule Of Thumb

If a design choice makes the system harder to explain, inspect, or evaluate before it clearly improves retrieval quality, defer it.
