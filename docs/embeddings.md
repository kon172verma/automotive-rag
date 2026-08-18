# Embeddings

This document records the embedding model choices we should consider for the project and the current recommendation.

## Goal

Choose an embedding model that:

- works well for manufacturer documentation retrieval
- is practical for iterative development
- fits hybrid RAG with keyword search plus dense retrieval
- leaves room for later quality comparisons

This document is only about the dense embedding model choice. It is not the reranker decision document.

## Recommendation

Start with `text-embedding-3-small` at `1536` dimensions.

Why:

- strong quality-to-cost tradeoff
- easy to adopt with a hosted API
- simpler than self-hosting an open embedding stack
- good enough for the phase we are in now, where chunking and retrieval design still matter more than squeezing out the last bit of embedding quality

## Models To Consider

### 1. OpenAI `text-embedding-3-small`

Recommendation: `Default v1 choice`.

Important points:

- model family: hosted OpenAI embedding model
- default dimensionality: `1536`
- can be shortened with the `dimensions` parameter
- current price shown in the model docs: `$0.02 / 1M input tokens`
- described by OpenAI as the small embedding model and the improved, more performant version of ada embeddings

Why it fits now:

- lower cost than `text-embedding-3-large`
- easier to iterate with while we are still tuning chunking, retrieval fusion, and reranking
- no extra model-hosting or inference infrastructure

Recommended usage for this repo:

- use `1536` dimensions first
- keep corpus and query embeddings on the same model and same dimension setting

### 2. OpenAI `text-embedding-3-large`

Recommendation: `Primary quality-upgrade path`.

Important points:

- model family: hosted OpenAI embedding model
- default dimensionality: `3072`
- can be shortened with the `dimensions` parameter
- current price shown in the model docs: `$0.13 / 1M input tokens`
- described by OpenAI as the most capable embedding model

Why it matters:

- strongest quality-focused OpenAI option for both English and non-English tasks
- good candidate once we have a stable evaluation set and want to measure whether better dense retrieval quality is worth the higher cost and storage footprint

Recommended usage for this repo:

- compare against `text-embedding-3-small` after the baseline is working
- use full `3072` dimensions if storage and latency are acceptable
- if vector size becomes a concern, evaluate shortened versions such as `1024` or `1536`

### 3. OpenAI `text-embedding-ada-002`

Recommendation: `Legacy reference only`.

Important points:

- dimensionality: `1536`
- older OpenAI embedding model
- still useful as a reference point, but not the preferred new choice for this project

Why not start here:

- OpenAI positions the `text-embedding-3` family as the newer path
- there is little reason to choose it for a new build unless compatibility constraints force it

### 4. `BAAI/bge-m3`

Recommendation: `Best later open-model comparison option`.

Important points:

- dimensionality: `1024` for dense embeddings
- max input length documented by the model authors: `8192`
- supports dense retrieval, lexical matching, and multi-vector retrieval modes
- multilingual and designed for multi-granularity retrieval

Why it is interesting:

- strong open-model option
- attractive if we later want self-hosting
- especially useful if we want to experiment with unified dense + sparse + multi-vector retrieval

Why not start here:

- adds model hosting and inference complexity
- adds more moving parts before our retrieval pipeline is fully stabilized
- our current hybrid plan already combines keyword retrieval and dense retrieval, so we do not need its unified sparse features on day one

## Comparison Table

| Model | Default / Native Dimensions | Hosted or Self-Hosted | Role In This Repo |
| --- | --- | --- | --- |
| `text-embedding-3-small` | `1536` | Hosted | `Default v1 choice` |
| `text-embedding-3-large` | `3072` | Hosted | `Main quality upgrade path` |
| `text-embedding-ada-002` | `1536` | Hosted | `Legacy reference only` |
| `BAAI/bge-m3` | `1024` dense | Self-hosted / open model | `Main later open-model comparison` |

## What Else Matters Besides Dimensions

### 1. Embeddings And Reranking Are Separate Stages

For this repo:

- the embedding model is the `bi-encoder`-style retrieval model
- the reranker is the `cross-encoder`-style relevance model

We should treat them as separate pipeline choices. The vector database stores embeddings, but reranking usually happens in the application pipeline unless a datastore offers a hosted reranker we intentionally adopt.

### 2. OpenAI v3 Embeddings Can Be Shortened

The `text-embedding-3-small` and `text-embedding-3-large` family supports the `dimensions` parameter.

That means we can:

- start with the default size
- reduce vector size later if storage or latency becomes an issue
- compare quality loss against cost savings in a controlled way

For this project, the default recommendation is still to start with the full default size rather than optimize early.

### 3. Normalization Affects Similarity Choice

OpenAI documents that embedding outputs are normalized to length 1, including shortened embeddings.

Practical implication:

- cosine similarity and dot product ranking are effectively aligned for OpenAI embeddings
- datastore configuration should stay consistent across indexing and query time

## Important Practical Rules

### 1. Re-embed Everything When The Embedding Setup Changes

If any of these change:

- embedding model
- embedding dimensions
- embedding text construction

then re-embed:

- all chunk embeddings
- all query embeddings

Do not mix old and new embeddings in the same retrieval space.

This is an engineering rule inferred from how embedding spaces work, not a product-specific API rule.

### 2. Keep Query And Chunk Embeddings Symmetric

Use the same:

- model
- dimensions
- preprocessing policy

for both chunk embeddings and query embeddings.

If later we test instruction-tuned open models with asymmetric query/document prompts, that should be treated as a deliberate experiment rather than the default setup.

### 3. Dense Embeddings Are Only One Part Of Hybrid RAG

Even a strong embedding model will not replace:

- metadata filtering
- keyword retrieval
- reranking
- clean chunking

This project should not over-attribute retrieval quality to the embedding model alone.

### 4. Dimensions Affect Cost, Storage, And Latency

Higher dimensions usually mean:

- more storage
- more memory pressure
- heavier vector indexing and retrieval

So the best model is not automatically the one with the largest vector.

### 5. Use Evaluation Before Upgrading

Do not switch from `text-embedding-3-small` to a larger or more complex alternative just because it sounds stronger.

Upgrade only after measuring:

- retrieval recall
- ranking quality
- answer quality
- cost and latency impact

## Recommended Path

1. Start with `text-embedding-3-small` at `1536`.
2. Build retrieval and evaluation around that baseline.
3. Compare against `text-embedding-3-large`.
4. Consider `BAAI/bge-m3` only after the hosted baseline is stable.

## References

- OpenAI model catalog: <https://developers.openai.com/api/docs/models/all>
- OpenAI `text-embedding-3-small` model page: <https://developers.openai.com/api/docs/models/text-embedding-3-small>
- OpenAI `text-embedding-3-large` model page: <https://developers.openai.com/api/docs/models/text-embedding-3-large>
- OpenAI embedding model announcement: <https://openai.com/index/new-embedding-models-and-api-updates/>
- OpenAI `text-embedding-ada-002` announcement: <https://openai.com/index/new-and-improved-embedding-model/>
- BGE-M3 model card: <https://huggingface.co/BAAI/bge-m3>
- BGE-M3 docs: <https://bge-model.com/bge/bge_m3.html>
