# Roadmap v1

This document tracks the path to `v1` for this repo.

The goal of `v1` is:

- a working end-to-end RAG system
- grounded answers with citations
- benchmark coverage for both:
  - latency
  - accuracy

This file focuses on:

- phases
- tasks
- current completion status
- what remains before `v1` is done

For component-specific design details, use the linked docs instead of this roadmap.

## v1 Goal Summary

| Area | v1 Target |
| --- | --- |
| Ingestion | Manuals can be converted into structured artifacts and loaded into the datastore |
| Retrieval | Hybrid retrieval works with keyword + dense search + reranking |
| Answering | A user can ask a question and receive a grounded answer with citations |
| Evaluation | We can measure retrieval quality and final answer quality on a gold dataset |
| Performance | We can measure component latency and end-to-end latency |

## Status Legend

| Status | Meaning |
| --- | --- |
| `Complete` | Implemented and usable in the repo today |
| `Partial` | Some pieces exist, but the phase is not yet sufficient for v1 |
| `Remaining` | Still needs implementation for v1 |

## Current Snapshot

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 0: Scope and design docs | `Complete` | Core design docs are present in `docs/` |
| Phase 1: Ingestion and chunk artifacts | `Complete` | Chunking pipeline and chunk artifacts exist |
| Phase 2: Embeddings and datastore load | `Complete` | Embeddings and PostgreSQL load flow exist |
| Phase 3: Retrieval baseline | `Complete` | Keyword, vector, fusion, and reranking are implemented |
| Phase 4: Retrieval evaluation | `Complete` | Gold datasets and retrieval evaluation runner exist |
| Phase 5: End-to-end answer generation | `Partial` | Initial OpenAI-backed answer generation CLI now exists, but answer-quality evaluation and tuning remain |
| Phase 6: Final answer evaluation | `Partial` | Ragas-backed answer evaluation now exists, but abstention coverage is still limited by the current datasets |
| Phase 7: Latency benchmarking and v1 release checks | `Partial` | Retrieval and generation latency instrumentation exist, but the full repeatable benchmark and release-gate workflow is not finished |

## Reference Docs

| Topic | Reference |
| --- | --- |
| Architecture overview | [architecture.md](./architecture.md) |
| Ingestion | [ingestion.md](./ingestion.md) |
| Chunking | [chunking.md](./chunking.md) |
| Datastore | [datastore.md](./datastore.md) |
| Embeddings | [embeddings.md](./embeddings.md) |
| Retrieval | [retrieval.md](./retrieval.md) |
| Answer generation | [generation.md](./generation.md) |
| Reranking | [reranking.md](./reranking.md) |
| Retrieval evaluation | [retrieval-evaluation.md](./retrieval-evaluation.md) |
| Evaluation strategy | [evaluation.md](./evaluation.md) |
| Evaluation dataset | [evaluation-dataset.md](./evaluation-dataset.md) |

## Phase 0: Scope and Design

| Task | Status | Notes |
| --- | --- | --- |
| Define project shape and baseline architecture | `Complete` | Covered in `docs/architecture.md` |
| Define retrieval-first strategy | `Complete` | Covered in `docs/retrieval.md` |
| Define evaluation-first strategy | `Complete` | Covered in `docs/evaluation.md` |
| Define chunking and metadata shape | `Complete` | Covered in `docs/chunking.md` and `docs/ingestion.md` |
| Define datastore direction | `Complete` | Covered in `docs/datastore.md` |

## Phase 1: Ingestion and Chunk Artifacts

| Task | Status | Notes |
| --- | --- | --- |
| Convert PDFs into structured document artifacts | `Complete` | Implemented in `src/chunking/create_chunks.py` |
| Build section-aware hierarchical chunk records | `Complete` | Implemented |
| Preserve page spans and heading paths | `Complete` | Implemented |
| Store document, section, and chunk metadata in artifacts | `Complete` | Implemented |
| Generate ingestion and chunking reports | `Complete` | Artifact reports are present |
| Improve extraction robustness on edge-case manuals | `Deferred to v1.1` | Useful hardening work, but not required to call the current baseline functional |

## Phase 2: Embeddings and Datastore Load

| Task | Status | Notes |
| --- | --- | --- |
| Generate embeddings from chunk artifacts | `Complete` | Implemented in `src/ingestion/create_embeddings.py` |
| Persist embedding artifacts separately from chunks | `Complete` | Implemented |
| Define PostgreSQL schema with keyword and vector support | `Complete` | Implemented in `db/init/002-create-schema.sql` |
| Load documents, sections, chunks, and vectors into PostgreSQL | `Complete` | Implemented in `src/ingestion/load_postgres.py` |
| Support idempotent reload / replacement of document data | `Complete` | Implemented through upsert and replace flow |
| Add production-style ingestion validation checks | `Deferred to v1.1` | Basic validation exists; broader integrity and regression checks remain |

## Phase 3: Retrieval Baseline

| Task | Status | Notes |
| --- | --- | --- |
| Resolve retrieval candidates by `make`, `model`, and `year` | `Complete` | Implemented |
| Implement keyword retrieval | `Complete` | Implemented |
| Implement dense retrieval | `Complete` | Implemented |
| Implement hybrid fusion | `Complete` | Implemented |
| Implement reranking | `Complete` | Implemented |
| Provide a CLI entry point for retrieval experiments | `Complete` | Implemented in `src/retrieval/search.py` |
| Add answer-context packaging for the future QA layer | `Complete` | Retrieval output can now be packaged into QA-ready evidence with citations and combined context text |

## Phase 4: Retrieval Evaluation

| Task | Status | Notes |
| --- | --- | --- |
| Create curated evaluation datasets | `Complete` | Present in `data/eval/` |
| Evaluate keyword, vector, hybrid, and hybrid-rerank modes | `Complete` | Implemented in `src/evaluation/evaluate.py` |
| Report Recall@k, MRR, section hit rate, and page hit rate | `Complete` | Implemented |
| Save machine-readable retrieval reports | `Complete` | Implemented |
| Add multi-chunk evidence coverage metrics | `Deferred to v1.1` | Current gold datasets only label one expected chunk per question, so v1 should stay any-hit based |
| Add structured latency reporting for retrieval stages | `Complete` | Retrieval reports now include machine-readable per-mode latency summaries |

## Phase 5: End-to-End Answer Generation

| Task | Status | Notes |
| --- | --- | --- |
| Build a QA layer that consumes retrieved evidence | `Complete` | Implemented through `src/generation/context_builder.py`, `src/generation/answering.py`, and `src/generation/cli.py` |
| Generate answers scoped to the requested vehicle | `Complete` | The initial generation flow consumes vehicle-scoped answer context |
| Return citations with page-aware evidence | `Complete` | The answer layer resolves citations from retrieved chunk metadata |
| Add abstention behavior when evidence is weak | `Partial` | Automatic abstention exists when evidence is missing; richer heuristics still need tuning |
| Define answer output schema for evaluation and debugging | `Complete` | Implemented through the structured output objects in `src/generation/models.py` |

## Phase 6: Final Answer Evaluation

| Task | Status | Notes |
| --- | --- | --- |
| Evaluate final answers separately from retrieval | `Complete` | Implemented in `src/evaluation/evaluate_answers.py` |
| Score answer correctness | `Complete` | Implemented with Ragas factual-correctness scoring against `reference_answer` |
| Score grounding / faithfulness | `Complete` | Implemented with Ragas faithfulness scoring against retrieved evidence |
| Score citation quality | `Complete` | Implemented with Ragas citation-quality scoring plus machine-readable citation hit checks |
| Score abstention quality on insufficient-evidence questions | `Partial` | The report tracks answerability and abstention outcomes, but the current gold datasets have little or no insufficient-evidence coverage |
| Produce machine-readable answer-eval reports | `Complete` | Answer-eval reports are written under `artifacts/answer-eval-reports` |

## Phase 7: Latency Benchmarks and v1 Release Checks

| Task | Status | Notes |
| --- | --- | --- |
| Measure keyword retrieval latency | `Complete` | Retrieval runs and evaluation reports already capture machine-readable keyword-stage latency |
| Measure dense retrieval latency | `Complete` | Retrieval runs and evaluation reports already capture machine-readable embedding and vector-search latency |
| Measure reranking latency | `Complete` | Retrieval runs and evaluation reports already capture reranker latency |
| Measure answer generation latency | `Partial` | Per-request generation latency is captured, but no aggregate benchmark workflow exists yet |
| Measure end-to-end latency | `Partial` | Retrieval and generation timings exist, but no formal end-to-end benchmark report is produced yet |
| Produce a repeatable benchmark report | `Partial` | Retrieval evaluation reports include aggregate latency summaries, but there is no dedicated end-to-end benchmark workflow yet |
| Define simple v1 release gate criteria | `Remaining` | Needed to call v1 done |

## What Is Already Done For v1

| Area | Already Done |
| --- | --- |
| Data preparation | Ingestion, chunking, document/section/chunk artifacts |
| Retrieval inputs | Embedding generation and PostgreSQL loading |
| Retrieval pipeline | Keyword search, vector search, fusion, reranking |
| Retrieval experimentation | CLI search flow |
| Retrieval evaluation | Gold datasets plus retrieval evaluation reports |
| Latency instrumentation | Structured retrieval-stage latency and per-request generation latency are captured |

## What Still Needs To Be Done For v1

| Priority | Remaining Work |
| --- | --- |
| High | Finish latency benchmarking and release-gate reporting |
| Medium | Add stronger insufficient-evidence coverage for abstention evaluation |
| Medium | Tune abstention behavior and citation quality |
| Medium | Keep retrieval evaluation stable for any-hit based metrics in v1 |

## Suggested Definition Of Done For v1

| Category | Done When |
| --- | --- |
| RAG flow | A user question can go from request -> retrieval -> reranking -> answer -> citations |
| Retrieval accuracy | Retrieval metrics are stable and reported on the gold dataset |
| Answer accuracy | Final answer metrics are reported on the gold dataset |
| Latency | Component-level and end-to-end latency reports are reproducible |
| Usability | The flow is runnable without ad hoc manual steps |

## Immediate Next Steps

| Order | Next Step |
| --- | --- |
| 1 | Add end-to-end latency benchmark scripts or reports |
| 2 | Define simple v1 release-gate criteria |
| 3 | Add stronger insufficient-evidence coverage for abstention evaluation |
| 4 | Tune abstention behavior and citation quality |
| 5 | Keep retrieval evaluation stable for any-hit based metrics in v1 |

## Handoff To v1.1

After the remaining benchmark and abstention work above is closed, the next milestone should be:

- [roadmap-v1.1.md](./roadmap-v1.1.md)

That milestone is where we should:

- benchmark alternative embedding, reranker, fusion, keyword, and answer-model choices
- compare structured retrieval and chunking variants
- choose stronger defaults before moving into deployment-oriented `v2`
