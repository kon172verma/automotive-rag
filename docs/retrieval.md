# Retrieval

This document defines the first retrieval pipeline we should build before adding answer generation.

## Goal

Build a retrieval pipeline that:

- takes a user question plus structured vehicle identity
- filters to the correct vehicle manual or manual set
- combines keyword and dense retrieval
- returns inspectable evidence with page-aware metadata
- can be measured before any LLM answer step

## Recommendation

Start with `hybrid retrieval` as the first implemented baseline.

That means:

- metadata filtering first
- keyword retrieval from PostgreSQL full-text search
- vector retrieval from `pgvector`
- score fusion across both result sets
- reranking after fusion, not before

## Why Retrieval Comes Before Generation

Recommendation: `Measure retrieval first`.

Why:

- if retrieval is weak, answer generation will hide the real problem
- retrieval metrics are easier to debug than end-to-end answer quality
- hybrid vs hierarchical comparisons are much cleaner at the retrieval layer

## Baseline Input

Each retrieval request should start with:

- `question`
- `make`
- `model`
- `year`

Example:

```json
{
  "question": "How do I check the engine oil?",
  "make": "toyota",
  "model": "camry",
  "year": 2023
}
```

## Baseline Retrieval Flow

### 1. Vehicle Filtering

First narrow the candidate set using metadata.

Recommended minimum filter behavior:

- require `make`, `model`, and `year` on every request
- resolve those fields to the expected manual or manual set
- filter retrieval candidates using those required vehicle fields before keyword or vector search
- never search across unrelated manuals unless the product intentionally supports that mode

Why:

- vehicle identity is a first-class retrieval signal in this project
- this prevents answers from blending across similar models and years

### 2. Keyword Retrieval

Use PostgreSQL full-text search over the chunk keyword text.

Recommended role:

- capture exact phrases
- capture warning light names
- capture part names
- capture manual terminology
- capture page-local procedural wording

Good examples:

- `malfunction indicator lamp`
- `tire pressure warning light`
- `vehicle identification number`
- `engine oil selection`

### 3. Dense Retrieval

Use `pgvector` over chunk embeddings.

Recommended role:

- capture semantically phrased questions
- handle paraphrases
- bridge user wording and manual wording
- support natural question phrasing better than keyword-only retrieval

Good examples:

- `How do I add oil if it is low?`
- `What should I do if the car overheats?`
- `How can I open the trunk from inside?`

### 4. Fusion

Combine keyword and vector candidates into one ranked list.

Recommendation: start with `Reciprocal Rank Fusion (RRF)`.

Why:

- simple
- robust
- easy to inspect
- does not require fragile score calibration between FTS and vector similarity

Good default behavior:

- retrieve top `k_keyword`
- retrieve top `k_vector`
- deduplicate by `chunk_id`
- fuse by RRF
- pass top fused candidates to reranking

### 5. Return Evidence, Not Answers

The retrieval layer should return:

- `chunk_id`
- `doc_id`
- `score`
- `retrieval_source`: keyword, vector, or fused
- `section_id`
- `heading_path`
- `page_start`
- `page_end`
- `chunk_text`

This makes retrieval debugging much easier than returning only IDs.

## Suggested v1 Retrieval Parameters

Use these only as a starting point:

- keyword top-k: `20`
- vector top-k: `20`
- fused candidate count before reranking: `20-30`
- final top-k after reranking: `5-10`

These values should be tuned using the evaluation set rather than assumed to be optimal.

## What Counts As A Good Retrieval Result

A good retrieval result should:

- include the correct chunk in the top results
- include the correct section even when the exact gold chunk is missed
- keep results inside the correct manual
- avoid returning many near-duplicate chunks
- keep page references interpretable

## What We Should Log

For every retrieval experiment, log:

- input question
- input `make`, `model`, and `year`
- metadata filter used
- keyword candidates
- vector candidates
- fused ranking
- reranked ranking
- whether the gold chunk was present before reranking
- whether the gold chunk was present after reranking

This is the minimum observability needed for useful retrieval tuning.

## What We Are Not Doing In v1

Not in the first retrieval implementation:

- hierarchical retrieval
- query rewriting
- multi-query retrieval
- agent loops
- cross-manual reasoning
- retrieval from images or OCR-only blocks as a separate subsystem

## Next Comparison

After the basic hybrid baseline is working, the first major comparison should be:

- basic hybrid retrieval
- hierarchical hybrid retrieval

The evaluation set should stay the same across both.
