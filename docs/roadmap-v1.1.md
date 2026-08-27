# Roadmap v1.1

This document defines the work immediately after `v1`.

`v1.1` is not the deployment milestone.

It is the `experimentation and benchmarking milestone` for the working end-to-end RAG pipeline.

The purpose of `v1.1` is to:

- close the important carryover work from `v1`
- benchmark the main retrieval and generation alternatives mentioned across the repo docs
- turn the current system into a repeatable experiment harness
- choose stronger defaults before making the system deployment-oriented in `v2`

## Goal

`v1.1` should answer:

- which bi-encoder / embedding setup is best for this corpus?
- which cross-encoder reranker is worth the latency?
- which answer model gives the best grounded QA tradeoff?
- which keyword, vector, fusion, and chunking variants actually help?
- which defaults should be locked before we split the system into more services?

## What v1.1 Is

`v1.1` is for:

- retrieval and answer-quality experiments
- benchmark coverage
- model comparisons
- ranking and chunking comparisons
- evaluation hardening
- latency, cost, and quality tradeoff analysis

## What v1.1 Is Not

`v1.1` is not for:

- full service decomposition
- LangGraph orchestration
- LangSmith-centric production tracing
- cloud deployment as the primary goal
- CI/CD rollout design
- replacing the local-first experimentation workflow with an ops-heavy stack

Those belong in `v2`.

## Inputs

This roadmap is based on:

- the current `v1` codebase and docs
- the remaining `v1` roadmap items
- the pasted external chat discussion about latency and optimization priorities
- the experimentation options already listed in:
  - [embeddings.md](./embeddings.md)
  - [retrieval.md](./retrieval.md)
  - [reranking.md](./reranking.md)
  - [chunking.md](./chunking.md)
  - [generation.md](./generation.md)
  - [evaluation.md](./evaluation.md)

## Success Criteria

`v1.1` is done when:

- the current pipeline can be benchmarked across multiple controlled variants
- answer, retrieval, latency, and citation reports are comparable across runs
- we can justify chosen defaults for embeddings, reranking, fusion, and answer models with measured results
- the remaining `v1` evaluation and benchmarking gaps are closed enough to move into `v2` with confidence

## Workstreams

### 1. v1 Carryover Closeout

These are the remaining items from `v1` that should either be completed or carried explicitly into the early `v1.1` cycle:

| Task | Why It Belongs In v1.1 |
| --- | --- |
| Add end-to-end latency benchmark scripts or reports | The system is already instrumented; we now need repeatable benchmark runs |
| Define simple v1 release-gate criteria | We need explicit go/no-go criteria before locking defaults |
| Add stronger insufficient-evidence coverage for abstention evaluation | Current answer-eval coverage is weak for this class |
| Tune abstention behavior and citation quality | The answer layer exists, but it still needs measured refinement |
| Keep retrieval evaluation stable for any-hit based metrics | This protects the baseline before broader experiments |

### 2. Evaluation Hardening

`v1.1` should strengthen the benchmark itself before we trust model comparisons too much.

| Task | Expected Outcome |
| --- | --- |
| Expand eval data with insufficient-evidence examples | Abstention evaluation becomes meaningful |
| Add multi-chunk evidence labels where needed | We can score questions that need multiple supporting chunks |
| Cover four core golden-dataset case types | We stop overfitting to single-chunk any-hit evaluation |
| Separate benchmark subsets by difficulty and category | Comparisons become easier to interpret |
| Track cost alongside latency and quality | Model comparisons become operationally useful |
| Add experiment metadata and run IDs to reports | Runs become reproducible and comparable |
| Add p50 / p95 / p99 summaries for major latency metrics | We stop relying on one-off request timings |

The four core golden-dataset cases for `v1.1` should be:

- single-chunk direct-answer questions
- multi-chunk same-section questions
- multi-chunk cross-section or cross-chapter questions
- no-answer or insufficient-evidence questions

### 3. Chunking and Context Experiments

The repo docs already point to several chunking and context options that are worth measuring now that the baseline works.

| Task | Expected Outcome |
| --- | --- |
| Compare current parent-child chunking against hierarchical retrieval variants | We learn whether structure-aware retrieval improves ranking |
| Test chunk target and ceiling variants | We quantify how chunk size affects recall, reranking, and answer quality |
| Evaluate table-heavy and specification-heavy chunk behavior | We verify whether current splitting is good enough for structured content |
| Compare sibling expansion and parent-section expansion at retrieval time | We measure whether local context recovery helps without storing overlap |
| Revisit index/TOC-aware hierarchy enrichment as a measured experiment | We test whether TOC structure improves section lineage and chunk organization |
| Add token-budgeted context assembly rules | We stop blindly sending expanded context to the answer model |

Recommended context-expansion checks:

- do not automatically expand every retrieved chunk to the full parent
- expand adjacent siblings only when a procedure or explanation appears truncated
- attach table headers when a row depends on them
- apply a hard context budget such as `2k-3k` tokens and compare quality vs latency

### 4. Dense Retrieval / Bi-Encoder Experiments

These come directly from [embeddings.md](./embeddings.md) and related docs.

| Track | Candidate Variants |
| --- | --- |
| Hosted OpenAI baseline comparison | `text-embedding-3-small` vs `text-embedding-3-large` |
| Dimension tradeoff comparison | `3072`, `1536`, `1024` where applicable |
| Legacy sanity reference | `text-embedding-ada-002` only if needed as a historical baseline |
| Open-model comparison | `BAAI/bge-m3` |
| Query/document-aware retrieval comparison | A Sentence Transformers retrieval model with asymmetric query/document behavior |
| Retrieval-oriented multimodal-ready comparison | `jina-embeddings-v4` if manual structure or visuals justify it later |
| Hosted-vs-local query embedding comparison | Measure whether moving query embeddings local materially improves latency without hurting quality |

Expected outcomes:

- dense retrieval recall comparisons
- latency and storage impact comparisons
- decision on whether the current OpenAI baseline stays the default

Specific latency-driven experiments worth running:

- investigate why single-query hosted embedding latency is high before changing models
- benchmark a long-lived OpenAI client vs any current one-request client setup
- compare hosted embeddings against a local query+corpus embedding stack
- if a local model is competitive on quality, evaluate making retrieval fully local

### 5. Keyword Retrieval Experiments

The current PostgreSQL FTS baseline should be improved by measured iteration before jumping to a different engine.

| Task | Expected Outcome |
| --- | --- |
| Improve `search_document` construction and field weighting | Better lexical relevance from section titles, headings, and chunk text |
| Compare tsquery construction variants | Better behavior for exact phrases, warning-light names, and short queries |
| Add phrase-heavy / terminology-heavy benchmark slices | Better visibility into lexical retrieval strengths and weaknesses |
| Test synonym or normalization improvements where justified | Better recall on user phrasing that differs from manual phrasing |
| Compare keyword candidate counts before fusion | Better tradeoff between recall and reranker latency |

Important rule:

- do not spend much time micro-optimizing BM25 latency unless benchmark evidence shows it has become a real bottleneck

### 6. Fusion Experiments

The docs already recommend RRF as the starting point. `v1.1` is where we test the alternatives.

| Task | Expected Outcome |
| --- | --- |
| Benchmark plain RRF across candidate-pool sizes | We understand the current fusion baseline better |
| Add weighted RRF experiments | We test whether keyword and vector branches should contribute unequally |
| Compare fused top-k sizes before reranking | We quantify recall-vs-latency tradeoffs |
| Track branch contribution diagnostics | We see when keyword or vector retrieval is doing the real work |

Recommended first weighted-RRF comparisons:

- keyword-heavy weighting for terminology and warning-light questions
- vector-heavy weighting for paraphrased procedural questions
- equal weighting as the baseline

### 7. Cross-Encoder / Reranker Experiments

These are already documented in [reranking.md](./reranking.md).

| Track | Candidate Variants |
| --- | --- |
| Current baseline | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| Stronger open-model comparison | `BAAI/bge-reranker-v2-m3` |
| Hosted reranker comparison | Cohere `rerank-v4.0` or `rerank-v3.5`, only if we want an API-managed path |
| Input formatting comparison | chunk text only vs chunk text + section title + heading path + vehicle context |
| Candidate pool comparison | rerank top `10`, `20`, `30` fused candidates |
| Runtime comparison | PyTorch CPU vs PyTorch MPS vs ONNX Runtime CPU for smaller rerankers |

Expected outcomes:

- precision gains from reranking
- latency cost of stronger rerankers
- decision on whether the current reranker should remain the default

Recommended first reranker latency experiments:

- reduce rerank candidate count before touching the model itself
- benchmark rerank `K=10`, `15`, `20`, `30`
- compare CPU vs MPS for small rerankers rather than assuming MPS always wins
- test ONNX export and quantization only after candidate-count tuning is measured

### 8. Answer Model Experiments

These come from [generation.md](./generation.md).

| Track | Candidate Variants |
| --- | --- |
| Default baseline | `gpt-5-mini` |
| Quality-focused comparison | `gpt-5.1` |
| Practical general baseline | `gpt-4o` |
| Simpler non-reasoning comparison | `gpt-4.1` |
| Prompt variants | stricter abstention and citation prompts |
| Evidence-budget variants | different `max_evidence_chunks` settings |
| Response-shape variants | concise answer style vs longer explanatory style |
| Streaming variants | streamed vs non-streamed answer delivery |

Expected outcomes:

- grounded answer quality comparisons
- citation discipline comparisons
- latency and cost comparisons
- decision on the default answer model for the next milestone

Generation-side benchmark priorities:

- break generation latency into:
  - request-to-first-token
  - total generation time
  - output token count
  - cached prompt tokens when available
  - tokens per second
- measure whether shorter answer formats materially improve latency
- compare models only after prompt and context budgets are reasonably controlled

### 9. Answer-Eval and Citation Experiments

The new answer-eval path exists now. `v1.1` should make it stronger.

| Task | Expected Outcome |
| --- | --- |
| Refine Ragas-backed answer evaluation | More trustworthy answer-quality measurements |
| Add stronger citation usefulness analysis | Better distinction between valid and genuinely helpful citations |
| Compare answerability heuristics | Better abstention behavior on weak-evidence questions |
| Add report summaries by model, category, and question type | Easier experiment review |
| Add prompt-caching visibility to generation reports | We can see whether stable prompt prefixes are reducing cost and latency |

### 10. Benchmark and Experiment Infrastructure

`v1.1` should make experimentation easy enough that the repo stops relying on ad hoc manual comparisons.

| Task | Expected Outcome |
| --- | --- |
| Add experiment configuration support | Swappable components without editing core code |
| Standardize report directories and run naming | Cleaner experiment tracking |
| Add summary reports across many runs | Easier winner/loser comparisons |
| Record latency, cost, and quality together | Practical component tradeoff analysis |
| Add one benchmark command set for retrieval-only and answer-eval runs | Repeatable local workflow |
| Record TTFT and generation-token metrics | LLM latency becomes diagnosable instead of opaque |
| Distinguish retrieval latency from wall-clock answer latency | End-to-end comparisons become more meaningful |

## Suggested Benchmark Matrix

Start simple. Do not combine too many moving parts in one run.

Recommended order:

1. lock the current `v1` baseline as the control
2. instrument generation latency more deeply:
   request-to-first-token, total generation time, output tokens, cached tokens
3. investigate and benchmark hosted embedding latency before replacing it
4. compare embeddings one at a time
5. compare rerankers one at a time, starting with candidate-count reduction
6. compare answer models one at a time
7. compare weighted RRF after the single-component baselines are understood
8. compare chunking / retrieval-time expansion variants only after the main ranking defaults are stable

## Decision Rules

Use these rules during `v1.1`:

- do not change two core retrieval layers at once unless the experiment explicitly requires it
- keep one frozen baseline for every comparison batch
- prefer measured improvements over intuition-driven complexity
- track latency and cost next to accuracy, not afterward
- move a change into the default path only if it wins clearly enough to justify added complexity
- do not optimize the already-fast parts of the pipeline before the slow API/model calls
- prefer instrument-first changes before swapping major components

## Out Of Scope

Out of `v1.1`:

- production service decomposition
- LangGraph workflow orchestration
- LangSmith-based production tracing as the main operating model
- cloud database migration
- CI/CD rollout
- AWS infrastructure packaging
- autoscaling and SLO design

Those belong in `v2`.

## Exit Criteria

| Area | v1.1 Done When |
| --- | --- |
| Retrieval defaults | Embedding, keyword, fusion, and reranker choices are backed by benchmark evidence |
| Answer defaults | The answer model and prompt path are backed by answer-eval results |
| Benchmarking | Retrieval, answer, latency, and citation reports are comparable across runs |
| Carryover closeout | The remaining `v1` benchmark and abstention gaps are resolved or explicitly retired |
| Readiness for v2 | We know which components are worth hardening, isolating, or serving separately |
