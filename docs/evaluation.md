# Evaluation

This document records how we will define answer quality and evaluate the pipeline.

## Goal

Evaluate both:

- retrieval quality
- final answer quality

The evaluation setup should help us compare:

- basic hybrid RAG
- hierarchical hybrid RAG later

## Core Decision

Recommendation: `Create a small, manual, high-quality evaluation set early`.

Why:

- without a test set, retrieval tuning becomes guesswork
- comparison between pipelines will be subjective
- a small good dataset is more useful than a large noisy one

## What A Good Answer Should Look Like

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

For the eval set specifically:

- `question` should read like a natural user question
- `question` should usually not repeat the full vehicle name if `vehicle_context` already carries it
- `reference_answer` should answer the question directly
- `reference_answer` should avoid repetitive phrasing such as `the manual says`
- `reference_answer` should include the actual value, instruction, or conclusion when the manual provides one

## What Citations Should Look Like

Recommendation:

- cite the source manual
- cite page numbers
- cite the most relevant supporting chunk, not just any retrieved chunk

If the answer depends on multiple manual sections, it should cite each relevant source.

## Do We Need A Sample Dataset?

Recommendation: `Yes, definitely`.

The first evaluation set should be small but intentional.

Suggested properties:

- start with `100` questions for `v1`
- use all `4` current manuals
- use `5` categories
- use `5` questions per category per model
- include both easy and tricky questions
- include model-specific questions
- include cases where the answer should be "not enough evidence"

Recommended `v1` shape:

- `4` models
- `5` categories
- `5` questions per category per model

This gives:

- `4 x 5 x 5 = 100` questions

## What Question Types Should Be In The Evaluation Set?

Include questions such as:

- maintenance
- warning lights
- troubleshooting
- specifications
- procedures

This mix will expose different retrieval failure modes.

## How Should We Evaluate Retrieval?

Recommendation: evaluate retrieval separately from generation.

Track:

- `Recall@k`
- `MRR` or `nDCG`
- whether the gold evidence appears before reranking
- whether the gold evidence appears after reranking

Why:

- it tells us whether failures come from retrieval or the LLM
- it makes hybrid vs hierarchical comparisons cleaner

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

## What Data Should Each Evaluation Example Contain?

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

This format will support both retrieval and answer evaluation.

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
  "question": "Where can I find the USB charging ports in the 2023 Toyota Camry?",
  "reference_answer": "The owner's manual lists USB charging ports under the 'Other interior features' area in the storage/features section.",
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
  "notes": "Good starter feature-location question. Useful for testing exact section and page retrieval."
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

## Example From Current Artifacts

Here is one concrete example grounded in the current chunk artifacts already loaded into PostgreSQL:

```json
{
  "question_id": "camry-2023-procedures-001",
  "doc_id": "2023-toyota-camry",
  "make": "toyota",
  "model": "camry",
  "year": 2023,
  "vehicle_context": "2023 Toyota Camry",
  "category": "procedures",
  "question": "Where does the manual discuss USB charging ports for the 2023 Toyota Camry?",
  "reference_answer": "The manual discusses USB charging ports in the interior/storage features area under 'Other interior features'.",
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
  "notes": "Good first retrieval example because the section label and pages are already visible in the chunk artifact."
}
```

## How Should We Build The 100 Questions?

Recommendation: fill the matrix deliberately instead of writing questions randomly.

Suggested `v1` matrix:

- `2020-toyota-yaris`: `5` questions each for maintenance, warning lights, troubleshooting, specifications, procedures
- `2023-toyota-camry`: `5` questions each for maintenance, warning lights, troubleshooting, specifications, procedures
- `2023-toyota-highlander`: `5` questions each for maintenance, warning lights, troubleshooting, specifications, procedures
- `2026-toyota-corolla`: `5` questions each for maintenance, warning lights, troubleshooting, specifications, procedures

This gives balanced coverage and makes later comparison cleaner.

## What Failure Cases Should We Watch Closely?

Track failures such as:

- wrong model/year retrieved
- right document but wrong section
- table missed by retrieval
- warning text outranked by generic explanation
- answer overstates what the manual says
- citations point to weak evidence

These failure labels will make later iteration much faster.

## Chosen Path

The recommended evaluation path is:

1. Define what a good grounded answer looks like.
2. Create a small gold evaluation set early.
3. Evaluate retrieval and answer generation separately.
4. Use the same dataset to compare basic hybrid and hierarchical hybrid later.
5. Keep human review central, with optional LLM assistance later.
