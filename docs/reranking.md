# Reranking

This document defines how reranking should fit into the first retrieval pipeline.

## Goal

Improve ranking quality after hybrid retrieval by scoring a smaller candidate set with a stronger relevance model.

## Recommendation

Recommendation: `Use reranking in v1`.

Why:

- keyword and vector retrieval each return partially relevant chunks
- manuals often contain many nearby chunks with similar wording
- reranking is one of the highest-leverage quality improvements for grounded QA

## Where Reranking Fits

The order should be:

1. vehicle metadata filter
2. keyword retrieval
3. vector retrieval
4. fusion
5. reranking
6. answer generation later

Do not rerank the whole corpus.

Reranking should only score a small fused candidate pool.

## Model Type

Recommendation: use a `cross-encoder-style reranker`.

Role:

- input: query plus chunk text together
- output: a relevance score for that pair

This differs from the embedding model:

- embeddings support fast independent encoding for large-scale retrieval
- rerankers support slower but more precise scoring on a small candidate set

## Candidate Pool Size

Recommendation: rerank only the top `20-30` fused candidates first.

Why:

- enough room for recovery if initial retrieval is imperfect
- small enough to keep latency manageable
- simple enough to inspect

## What The Reranker Should See

Recommendation: rerank using:

- question text
- chunk text
- selected metadata that improves relevance interpretation

Good metadata to include in the reranker input if needed:

- heading path
- section title
- vehicle context

Do not overload the reranker with large metadata blobs unless evaluation shows it helps.

## What Good Reranking Should Improve

Reranking should improve:

- whether the best chunk reaches rank 1-3
- whether procedural chunks outrank broad overview chunks
- whether exact answer-bearing chunks outrank TOC-style chunks
- citation precision

It should not:

- change the candidate set itself
- compensate for completely broken metadata filtering
- be used as a substitute for good chunking

## What We Should Measure

Compare:

- fused ranking before reranking
- ranking after reranking

Track at least:

- `Recall@k`
- `MRR`
- gold chunk rank before rerank
- gold chunk rank after rerank

If reranking does not improve ranking quality enough to justify latency, we should say so explicitly.

## Observability

For every eval example, keep:

- fused candidate list
- reranked candidate list
- reranker scores
- gold hit position before rerank
- gold hit position after rerank

This is important because rerankers can sometimes:

- help precision
- slightly hurt recall at shallow `k`
- over-favor short or highly lexical chunks

## v1 Rule Of Thumb

Recommendation:

- keep reranking simple
- add one reranker
- compare before vs after
- avoid tuning too many moving parts at once

The first question is not:

- `What is the strongest reranker in theory?`

The first question is:

- `Does reranking materially improve retrieval quality on our evaluation set?`

## What We Are Deferring

Not in the first reranking phase:

- listwise reranking
- section-level reranking as a separate subsystem
- answer-aware reranking
- multi-stage learned ranking stacks
- LLM reranking in the main baseline
