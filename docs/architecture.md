# Architecture

This document captures the top-level architecture choices for the project.

## Project Shape

We will divide the project into three parts:

1. Data ingestion
2. Sample QA and evaluation
3. Document retrieval and answer generation

We will finalize these docs before making implementation changes.

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

## Chosen Path

The recommended path for this repo is:

1. Design the ingestion format so it supports both basic hybrid and hierarchical hybrid later.
2. Build a sample evaluation set early.
3. Implement basic hybrid RAG as the first working system.
4. Add hierarchical hybrid retrieval as the first major comparison.
5. Keep advanced patterns deferred unless the data proves they help.

## What We Are Deferring

Defer these until the basics are working well:

- GraphRAG
- agentic workflows
- multi-hop reasoning across many manuals
- web search augmentation
- broad non-manufacturer automotive knowledge

## Rule Of Thumb

If a design choice makes the system harder to explain, inspect, or evaluate before it clearly improves retrieval quality, defer it.
