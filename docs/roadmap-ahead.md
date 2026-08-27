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
| `v1.1` | Run structured experiments and benchmarks across alternative components, and close the remaining v1 benchmark gaps |
| `v2` | Make the system deployment-ready with service boundaries, LangGraph orchestration, LangSmith tracing, cloud infrastructure, and CI/CD |
| `v2.1` | Scale and harden the deployed architecture after the first production-ready shape is working |

## Reference Docs

| Topic | Reference |
| --- | --- |
| v1.1 experiment roadmap | [roadmap-v1.1.md](./roadmap-v1.1.md) |
| v2 target architecture | [v2.md](./v2.md) |
| Retrieval | [retrieval.md](./retrieval.md) |
| Reranking | [reranking.md](./reranking.md) |
| Embeddings | [embeddings.md](./embeddings.md) |
| Datastore | [datastore.md](./datastore.md) |
| Evaluation | [evaluation.md](./evaluation.md) |
| Retrieval evaluation | [retrieval-evaluation.md](./retrieval-evaluation.md) |

## v1.1: Component Experiments and Benchmarking

### Goal

Turn the working v1 system into a reliable experimentation platform and finish the remaining benchmark-quality work from v1.

### Scope Table

| Track | Examples |
| --- | --- |
| v1 carryover hardening | End-to-end latency benchmarks, abstention coverage, release-gate criteria |
| Reranker experiments | Different cross-encoder rerankers |
| QA model experiments | Different LLMs for answer generation |
| Dense retrieval experiments | Different embedding models |
| Keyword retrieval experiments | Different full-text search techniques or query construction |
| Fusion experiments | Different fusion strategies, weighted RRF, and candidate sizes |
| Chunking and context experiments | Hierarchical variants, sibling expansion, parent-section expansion |
| Evaluation experiments | Stronger answer-quality, citation, abstention, and evidence-coverage metrics |

### Task Table

| Task | Outcome |
| --- | --- |
| Close the important v1 benchmark gaps | v1 exits cleanly into the experiment phase |
| Add experiment configuration support | We can swap components without rewriting the pipeline |
| Compare multiple rerankers | We can measure quality vs latency tradeoffs |
| Compare multiple answer models | We can measure correctness, grounding, and cost tradeoffs |
| Compare embedding models | We can measure dense retrieval quality changes |
| Compare keyword search variants | We can measure whether lexical retrieval improves |
| Compare fusion and weighted-RRF variants | We can justify the default fusion logic with evidence |
| Compare chunking and retrieval-time context expansion variants | We can test whether structure-aware changes help enough to matter |
| Add stronger benchmark reporting | We can compare runs consistently |
| Add experiment summaries | We can document the winning combinations clearly |

### Exit Criteria

| Area | v1.1 Done When |
| --- | --- |
| Experimentation | Component swaps are easy and repeatable |
| Benchmarking | Accuracy and latency reports are comparable across runs |
| Decision-making | We can justify chosen defaults with measured evidence |
| v1 carryover | Remaining v1 benchmark and abstention gaps are resolved or explicitly retired |

## v2: Deployment-Ready Architecture

### Goal

Move the system from a local experimentation platform to a deployment-ready architecture with clear service boundaries, cloud infrastructure, workflow orchestration, tracing, and CI/CD.

### Scope Table

| Service Candidate | Why Extract It |
| --- | --- |
| Embedding service | Different scaling profile and model-serving requirements |
| QA service | Separate model/runtime concerns from retrieval orchestration |
| Workflow/API service | Keep orchestration separate from heavy model inference |
| Evaluation worker | Long-running offline jobs should not share the online path |
| Managed cloud database | Production-ready datastore operations and reliability |
| CI/CD and infra layer | Repeatable deploys and environment promotion |

### Task Table

| Task | Outcome |
| --- | --- |
| Define service boundaries | Clear ownership of responsibilities |
| Containerize extracted components | Each component can run independently |
| Define internal APIs | Components can communicate in a stable way |
| Introduce LangGraph for bounded workflow orchestration | Online request flow becomes stateful and explicit |
| Add LangSmith and tracing-first observability | Runs, experiments, and failures are inspectable across components |
| Introduce async jobs where useful | Ingestion and eval stop blocking online flows |
| Add service-level observability | Each major component becomes measurable |
| Move to a cloud database instance | The datastore becomes deployment-ready |
| Add CI/CD and environment promotion | The system can be deployed and updated reliably |
| Add deployment-ready configuration | Easier transition to AWS hosting |

### Exit Criteria

| Area | v2 Done When |
| --- | --- |
| Separation | Major model-heavy components no longer have to run in-process |
| Deployment | Components can be deployed independently |
| Observability | Service-level latency and errors are visible |
| Reliability | A failure in one heavy component does not take down the whole flow |
| Operations | CI/CD, environment promotion, and cloud datastore management are in place |

## v2.1: Scale and Harden the Deployed System

### Goal

Refine the deployment-ready v2 system so it scales more cleanly and behaves better under production load.

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
| Expand the golden dataset beyond the `v1.1` core four cases | Evaluation coverage grows to include table lookup, heading-dependent, distractor, variant-sensitive, comparison, and other harder answer patterns |

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
| 1 | Finish `v1` first with end-to-end QA plus baseline evaluation |
| 2 | Use `v1.1` to identify which components are worth changing and which defaults should stay |
| 3 | Build `v2` around deployment readiness, not around speculative service splits |
| 4 | Use `v2.1` to scale or isolate only the services that actually need it after the first deployable architecture is working |

## Rule Of Thumb

| Situation | Recommendation |
| --- | --- |
| A component is still changing often | Keep it easier to experiment with first |
| A component has a different runtime or hardware profile | Consider splitting it into its own service |
| A component becomes a latency bottleneck | Measure it first, then isolate or scale it |
| A component fails independently from the rest of the system | Give it stronger service boundaries |
