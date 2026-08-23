<!-- markdownlint-disable MD024 -->

# Roadmap Ahead

This document tracks the planned work after `v1`.

The purpose of these next milestones is to:

- improve benchmark quality
- compare alternative components
- move from a single-process baseline toward service-oriented deployment
- make the system easier to scale

## Milestone Summary

| Milestone | Main Goal |
| --- | --- |
| `v1.1` | Run structured experiments and benchmarks across alternative components |
| `v2` | Extract the right components into separate services and containers |
| `v2.1` | Break services down further so the system scales more cleanly |

## Reference Docs

| Topic | Reference |
| --- | --- |
| v2 target architecture | [v2.md](./v2.md) |
| Retrieval | [retrieval.md](./retrieval.md) |
| Reranking | [reranking.md](./reranking.md) |
| Embeddings | [embeddings.md](./embeddings.md) |
| Datastore | [datastore.md](./datastore.md) |
| Evaluation | [evaluation.md](./evaluation.md) |
| Retrieval evaluation | [retrieval-evaluation.md](./retrieval-evaluation.md) |

## v1.1: Component Experiments and Benchmarking

### Goal

Turn the working v1 system into a reliable experimentation platform.

### Scope Table

| Track | Examples |
| --- | --- |
| Reranker experiments | Different cross-encoder rerankers |
| QA model experiments | Different LLMs for answer generation |
| Dense retrieval experiments | Different embedding models |
| Keyword retrieval experiments | Different full-text search techniques or query construction |
| Fusion experiments | Different fusion strategies and candidate sizes |
| Evaluation experiments | Stronger answer-quality and evidence-coverage metrics |

### Task Table

| Task | Outcome |
| --- | --- |
| Add experiment configuration support | We can swap components without rewriting the pipeline |
| Compare multiple rerankers | We can measure quality vs latency tradeoffs |
| Compare multiple answer models | We can measure correctness, grounding, and cost tradeoffs |
| Compare embedding models | We can measure dense retrieval quality changes |
| Compare keyword search variants | We can measure whether lexical retrieval improves |
| Add stronger benchmark reporting | We can compare runs consistently |
| Add experiment summaries | We can document the winning combinations clearly |

### Exit Criteria

| Area | v1.1 Done When |
| --- | --- |
| Experimentation | Component swaps are easy and repeatable |
| Benchmarking | Accuracy and latency reports are comparable across runs |
| Decision-making | We can justify chosen defaults with measured evidence |

## v2: Extract Services For Major Components

### Goal

Move the system from a single-process baseline to a service-oriented architecture where the right components run in separate containers or services.

### Scope Table

| Service Candidate | Why Extract It |
| --- | --- |
| Embedding service | Different scaling profile and model-serving requirements |
| QA service | Separate model/runtime concerns from retrieval orchestration |
| Workflow/API service | Keep orchestration separate from heavy model inference |
| Evaluation worker | Long-running offline jobs should not share the online path |

### Task Table

| Task | Outcome |
| --- | --- |
| Define service boundaries | Clear ownership of responsibilities |
| Containerize extracted components | Each component can run independently |
| Define internal APIs | Components can communicate in a stable way |
| Introduce async jobs where useful | Ingestion and eval stop blocking online flows |
| Add service-level observability | Each major component becomes measurable |
| Add deployment-ready configuration | Easier transition to AWS hosting |

### Exit Criteria

| Area | v2 Done When |
| --- | --- |
| Separation | Major model-heavy components no longer have to run in-process |
| Deployment | Components can be deployed independently |
| Observability | Service-level latency and errors are visible |
| Reliability | A failure in one heavy component does not take down the whole flow |

## v2.1: Decompose Services For Scalability

### Goal

Refine the v2 service layout so the system scales more cleanly under higher traffic.

### Scope Table

| Decomposition Candidate | Example |
| --- | --- |
| Reranker service | Separate local reranker process or container |
| Retrieval path split | Different handling for keyword and dense retrieval paths |
| Worker separation | Separate ingestion, evaluation, and backfill workers |
| Caching and hot-path support | Dedicated cache-aware online components |

### Task Table

| Task | Outcome |
| --- | --- |
| Split reranker into its own service if locally hosted | Independent scaling and model lifecycle management |
| Separate online vs offline workloads more clearly | Better stability under load |
| Tune service autoscaling boundaries | Better cost/performance control |
| Add per-service SLOs | Scalability work becomes measurable |
| Add degraded-mode behavior | The system can continue operating during partial failures |

### Exit Criteria

| Area | v2.1 Done When |
| --- | --- |
| Scalability | Hot services can scale independently |
| Isolation | Heavy inference paths are isolated from orchestration |
| Resilience | Degraded-mode behavior exists for partial outages |
| Operations | Per-service metrics and SLOs are defined |

## Sequence Recommendation

| Order | Recommendation |
| --- | --- |
| 1 | Finish `v1` first with end-to-end QA plus benchmarks |
| 2 | Use `v1.1` to identify which components are worth changing |
| 3 | Build `v2` service boundaries around components that proved important |
| 4 | Use `v2.1` to scale or isolate only the services that actually need it |

## Rule Of Thumb

| Situation | Recommendation |
| --- | --- |
| A component is still changing often | Keep it easier to experiment with first |
| A component has a different runtime or hardware profile | Consider splitting it into its own service |
| A component becomes a latency bottleneck | Measure it first, then isolate or scale it |
| A component fails independently from the rest of the system | Give it stronger service boundaries |
