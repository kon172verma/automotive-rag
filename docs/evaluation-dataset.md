# Evaluation Dataset

This document defines the structure and purpose of the curated evaluation dataset.

## Goal

Create a small, high-quality evaluation set that we can use to:

- test retrieval quality
- test final answer quality later
- compare basic hybrid RAG and hierarchical hybrid RAG on the same questions

## Core Decision

Recommendation: `Create a manual evaluation set early`.

Why:

- without a test set, retrieval tuning becomes guesswork
- comparison between pipelines becomes subjective
- a small, trusted dataset is more useful than a large noisy one

## v1 Dataset Shape

Recommendation:

- start with `100` questions
- use all `4` current manuals
- use `5` categories
- use `5` questions per category per model

This gives:

- `4 x 5 x 5 = 100` questions

## Question Types

Include questions such as:

- maintenance
- warning lights
- troubleshooting
- specifications
- procedures

This mix exposes different retrieval failure modes and different answer styles.

## Question And Answer Style

For the eval set specifically:

- `question` should read like a natural user question
- `question` should usually not repeat the full vehicle name if `vehicle_context` already carries it
- `reference_answer` should answer the question directly
- `reference_answer` should avoid repetitive phrasing such as `the manual says`
- `reference_answer` should include the actual value, instruction, or conclusion when the manual provides one

## What Data Each Example Should Contain

Suggested fields:

- `question_id`
- `doc_id`
- `make`
- `model`
- `year`
- `vehicle_context`
- `category`
- `question`
- `reference_answer`
- `expected_sections`
- `expected_pages`
- `expected_chunk_ids`
- `answerability`
- `difficulty`
- `notes`

This format supports both retrieval evaluation and final answer evaluation later.

## What Are Gold Labels?

Gold labels are the trusted correct references we use to evaluate the system.

In this repo, gold labels can include:

- the correct vehicle context
- the correct source manual
- the correct section or sections
- the correct page or page range
- the correct chunk IDs when known
- a short reference answer grounded in the manual

These labels let us evaluate:

- whether retrieval found the right evidence
- whether the answer stayed grounded
- whether citations point to the right place

## Recommended Eval Schema

Recommendation: store the first evaluation set as JSON.

Suggested shape for each example:

```json
{
  "question_id": "camry-2023-feature-001",
  "doc_id": "2023-toyota-camry",
  "make": "toyota",
  "model": "camry",
  "year": 2023,
  "vehicle_context": "2023 Toyota Camry",
  "category": "procedures",
  "question": "Where can I find the USB charging ports?",
  "reference_answer": "USB charging ports are listed under the storage and interior features area.",
  "expected_sections": [
    "5-3. Using the storage features"
  ],
  "expected_pages": [
    5,
    6
  ],
  "expected_chunk_ids": [
    "2023-toyota-camry::p0004::c0000"
  ],
  "answerability": "answerable",
  "difficulty": "easy",
  "notes": "Good starter feature-location question."
}
```

Field guidance:

- `question_id`: stable identifier used in reports and experiments
- `doc_id`: the expected manual when the question is answerable
- `vehicle_context`: user-facing vehicle string used by the pipeline
- `category`: one of the chosen eval categories
- `reference_answer`: short human-written gold answer, not a long quote
- `expected_sections`: one or more manual sections that should support the answer
- `expected_pages`: expected page numbers or the main page span
- `expected_chunk_ids`: optional but very useful for retrieval metrics
- `answerability`: `answerable` or `insufficient_evidence`
- `difficulty`: simple human label like `easy`, `medium`, or `hard`
- `notes`: short evaluator note, especially for ambiguity or edge cases

## Current Dataset Location

The current per-model eval files live under:

- `data/eval/`

Today they are split by vehicle manual so they are easier to inspect and revise.
