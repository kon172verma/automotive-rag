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

- around 30 to 60 questions to start
- spread across the available manuals
- include both easy and tricky questions
- include model-specific questions
- include cases where the answer should be "not enough evidence"

## What Question Types Should Be In The Evaluation Set?

Include questions such as:

- troubleshooting
- warning light interpretation
- maintenance schedule lookups
- fluid and tire questions
- feature usage questions
- specification lookups
- ambiguous vehicle-context questions
- negative or abstention cases

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
- `vehicle_context`
- `question`
- `expected_answer_summary`
- `gold_document_id`
- `gold_page_span`
- `gold_section_id` when known
- `answerability`
- `question_type`
- `notes`

This format will support both retrieval and answer evaluation.

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
