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

- [docs/retrieval-evaluation.md](/Users/konark/Desktop/Personal/automotive-rag/docs/retrieval-evaluation.md)

## How Should We Evaluate Final Answers?

Use a small rubric with human review.

Recommended answer dimensions:

- correctness
- grounding
- citation quality
- completeness
- vehicle specificity
- clarity
- abstention quality when evidence is missing

Simple scoring is enough at first, as long as it is consistent.

## Should We Use LLM-as-Judge?

Recommendation: `Only as a secondary aid`.

Why:

- it can help scale review
- but it should not be the source of truth early on
- human inspection matters a lot in a grounded QA project

Use human-reviewed examples as the primary benchmark.

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

- [docs/evaluation-dataset.md](/Users/konark/Desktop/Personal/automotive-rag/docs/evaluation-dataset.md)

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
