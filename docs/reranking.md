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

## How We Run It

Recommendation: run the first reranker as a `separate host service`.

For this repo, the implementation should:

- use `sentence-transformers`
- run a long-lived `CrossEncoder` process on the host
- let the retrieval code call that service over local HTTP
- score only the top fused candidates
- keep the database responsible only for retrieval, not reranking

Why this is the right fit now:

- avoids loading reranker weights on every retrieval run
- keeps the reranker lifecycle isolated from retrieval orchestration
- lets Apple Silicon Macs use `MPS` when the service runs on the host
- stays simple enough for local debugging and before-vs-after evaluation

Operational notes:

- the model weights are downloaded on first service startup and then cached locally
- the service should prefer `MPS` on compatible macOS hosts, then `CUDA`, then `CPU`
- we are not making Docker the default reranker runtime on macOS because that would give up `MPS`

## Rerankers To Consider

### 1. `cross-encoder/ms-marco-MiniLM-L6-v2`

Recommendation: `Default v1 reranker to try first`.

Why it fits now:

- simple and well-known cross-encoder baseline
- easy to run locally with Sentence Transformers
- strong enough to validate whether reranking is helping at all
- lighter than larger rerankers, which makes early iteration easier

Why it is not automatically the long-term choice:

- it is primarily an English MS MARCO-style reranker
- it is a practical baseline, not necessarily the best production endpoint for every future manual set

### 2. `BAAI/bge-reranker-v2-m3`

Recommendation: `Main stronger open-model comparison`.

Why it is interesting:

- purpose-built reranker rather than a generic embedding model
- multilingual
- stronger long-term fit if we later support more languages or want a more retrieval-focused open reranker

Why not start here immediately:

- larger and a bit heavier operationally than a small MiniLM reranker
- adds more inference complexity before we have measured whether reranking helps enough to matter

### 3. Cohere `rerank-v4.0` or `rerank-v3.5`

Recommendation: `Main hosted reranker option if we want an API-managed second stage`.

Why it is interesting:

- easy hosted integration
- designed specifically for second-stage reranking
- useful if we want to compare local open rerankers against a managed API option

Why not make it the default right now:

- introduces another external vendor into the pipeline
- adds usage cost and another API dependency
- we should first confirm the value of reranking with a simpler baseline

## Current Recommendation

Recommendation for this repo:

1. start with `cross-encoder/ms-marco-MiniLM-L6-v2`
2. measure before-vs-after reranking on the current eval set
3. compare later against `BAAI/bge-reranker-v2-m3`
4. consider Cohere rerank only if we specifically want a hosted reranker path

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

## References

- Sentence Transformers retrieve-and-rerank guide: <https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html>
- Sentence Transformers cross-encoder pretrained models: <https://www.sbert.net/docs/cross_encoder/pretrained_models.html>
- `cross-encoder/ms-marco-MiniLM-L6-v2` model card: <https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2>
- `BAAI/bge-reranker-v2-m3` model card: <https://huggingface.co/BAAI/bge-reranker-v2-m3>
- Cohere rerank overview: <https://docs.cohere.com/docs/rerank-overview>
- Cohere reranking best practices: <https://docs.cohere.com/docs/reranking-best-practices>
