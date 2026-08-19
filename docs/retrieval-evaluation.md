# Retrieval Evaluation

This document defines how we should evaluate the retrieval pipeline before answer generation.

## Goal

Measure whether the system retrieves the right manual evidence for each evaluation question.

This evaluation comes before:

- final answer generation
- citation formatting quality checks
- end-to-end LLM answer scoring

## Recommendation

Recommendation: `Evaluate retrieval in stages`.

Compare:

1. keyword retrieval only
2. vector retrieval only
3. hybrid fused retrieval
4. hybrid retrieval plus reranking

This will show which layer is actually helping.

## Evaluation Inputs

Use the curated evaluation dataset in `data/eval/`.

Each example gives us:

- natural user question
- vehicle context
- gold manual
- gold section
- gold pages
- gold chunk IDs when known

These labels are enough to evaluate retrieval before LLM generation exists.

## Core Metrics

### 1. Recall@k

Recommendation: make this the first metric we trust.

Interpretation:

- did at least one gold chunk appear in the top `k` results?

Suggested checkpoints:

- `Recall@1`
- `Recall@3`
- `Recall@5`
- `Recall@10`

### 2. MRR

Recommendation: use `MRR` after Recall@k is working.

Interpretation:

- how early did the first relevant result appear?

This is useful because two systems can have the same recall but very different ranking quality.

### 3. Section Hit Rate

Recommendation: track this separately.

Interpretation:

- did the system retrieve the correct section even if it missed the exact gold chunk?

This matters because chunk boundaries are imperfect and some questions can be answered from multiple sibling chunks inside one section.

### 4. Page Hit Rate

Recommendation: track page overlap separately.

Interpretation:

- did the retrieved evidence land on the right page or page span?

This is useful for citation quality and for spotting section-level drift.

## Before And After Reranking

For each experiment, log:

- retrieval results before reranking
- retrieval results after reranking

This helps answer:

- did reranking improve early precision?
- did reranking rescue good candidates from lower fused ranks?
- did reranking accidentally suppress gold evidence?

## Matching Rules

Use clear matching rules from the beginning.

Recommended v1 matching:

- `gold chunk hit`: any `expected_chunk_id` appears in top `k`
- `gold section hit`: any retrieved result matches an `expected_section`
- `gold page hit`: any retrieved result overlaps an `expected_page` span

Keep these metrics separate in reports.

## Recommended Experiment Reports

Each retrieval run should produce a machine-readable report containing:

- dataset used
- retrieval configuration
- top-k settings
- whether reranking was enabled
- aggregate metrics
- per-question results

Per-question results should include:

- question ID
- question text
- vehicle context
- gold chunk IDs
- retrieved chunk IDs before reranking
- retrieved chunk IDs after reranking
- hit or miss labels

## Useful Error Buckets

When reviewing failures, classify them roughly as:

- wrong manual
- right manual, wrong section
- right section, wrong sibling chunk
- keyword miss
- semantic miss
- fusion miss
- reranker regression

These buckets are more actionable than a generic `failed retrieval`.

## Success Criteria For The First Baseline

We do not need perfect retrieval immediately.

A good first baseline should:

- consistently stay inside the correct manual
- achieve strong recall on direct lookup questions
- perform reasonably on troubleshooting and procedure questions
- improve after reranking in a measurable way

## What We Are Not Evaluating Yet

Not in this phase:

- answer fluency
- final citation formatting
- conversation memory
- multi-turn clarification quality
- hallucination behavior in the answer model

Those come after retrieval is measurable.
