# Evaluation

This document records the top-level evaluation strategy for the project.

## Goal

Evaluate both:

- retrieval quality
- final answer quality

The evaluation setup should help us compare:

- basic hybrid RAG
- hierarchical hybrid RAG later

## Why Evaluation Matters Early

Recommendation: `Define evaluation before building the full answer pipeline`.

Why:

- retrieval tuning becomes guesswork without a trusted test set
- answer generation can hide retrieval failures
- system comparisons are much cleaner when we use the same dataset and metrics throughout

## What A Good Final Answer Should Look Like

A good answer should be:

- correct relative to the manual
- grounded in retrieved evidence
- scoped to the specified vehicle
- clear and concise
- actionable when the manual supports action
- explicit about uncertainty or missing evidence
- accompanied by useful citations

It should not:

- invent unsupported steps
- blend answers across the wrong model or year
- hide uncertainty
- cite irrelevant pages
- read like an annotation note instead of an answer

## What Citations Should Look Like

Recommendation:

- cite the source manual
- cite page numbers
- cite the most relevant supporting chunk, not just any retrieved chunk

If the answer depends on multiple manual sections, it should cite each relevant source.

## How Should We Evaluate Retrieval?

Recommendation: evaluate retrieval separately from generation.

Why:

- it tells us whether failures come from retrieval or the LLM
- it makes hybrid vs hierarchical comparisons cleaner

For retrieval-only metrics and reporting, see:

- [docs/retrieval-evaluation.md](./retrieval-evaluation.md)

## How Should We Evaluate Final Answers?

Recommendation: use a `machine-readable answer-eval pipeline` first, then spot-check with humans.

The current Phase 6 direction is:

- use `ragas` for answer correctness, grounding, and answer relevance
- score citation quality with `ragas` plus explicit citation-hit checks
- track answerability and abstention behavior separately
- save one JSON report per evaluation run

Recommended answer dimensions:

- correctness relative to the gold reference answer
- grounding / faithfulness to retrieved manual evidence
- citation quality
- answer relevance to the user question
- answerability / abstention behavior

Human review still matters, especially for:

- borderline partial answers
- citation usefulness
- insufficient-evidence questions

## Should We Use LLM-as-Judge?

Recommendation: `Yes, with guardrails`.

Why:

- it scales much better than pure manual review
- `ragas` gives us consistent machine-readable answer metrics
- we still keep reference answers, expected sections, and citation hits in the loop

The practical rule should be:

- use `ragas` as the default scoring layer
- use human spot checks for regressions, prompt changes, and surprising failures

## How Should We Compare Basic Hybrid vs Hierarchical Hybrid?

Recommendation:

- use the same evaluation set
- log retrieval outputs before reranking
- log retrieval outputs after reranking
- compare answer quality separately from retrieval quality

Focus on whether hierarchical structure actually helps:

- section targeting
- long-procedure questions
- maintenance schedule lookups
- citation precision

## Evaluation Dataset

Recommendation: keep the eval dataset design separate from metric definitions.

For dataset shape, schema, and gold-label guidance, see:

- [docs/evaluation-dataset.md](./evaluation-dataset.md)

## Current Example

One example from the current curated dataset:

```json
{
  "question_id": "camry-2023-procedures-001",
  "doc_id": "2023-toyota-camry",
  "make": "toyota",
  "model": "camry",
  "year": 2023,
  "vehicle_context": "2023 Toyota Camry",
  "category": "procedures",
  "question": "How do I open the trunk from inside?",
  "reference_answer": "Press and hold the trunk opener switch.",
  "expected_sections": [
    "Opening the trunk from inside the vehicle"
  ],
  "expected_pages": [
    {
      "start": 156,
      "end": 156
    }
  ],
  "expected_chunk_ids": [
    "2023-toyota-camry::p0237::c0000"
  ],
  "answerability": "answerable",
  "difficulty": "easy",
  "notes": "Simple procedural question with a short answer-bearing chunk."
}
```

This is the style we should continue using as the evaluation set grows.

## Chosen Path

The recommended evaluation path is:

1. Define what a good grounded answer looks like.
2. Create a small gold evaluation set early.
3. Evaluate retrieval and answer generation separately.
4. Use the same dataset to compare basic hybrid and hierarchical hybrid later.
5. Keep human review central, with optional LLM assistance later.
