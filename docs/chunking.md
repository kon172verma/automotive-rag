# Chunking

This document records the chunking strategies considered for the manuals and the recommended path for this project.

## Goal

Choose a chunking strategy that:

- works well for hybrid retrieval
- keeps chunks understandable and debuggable
- preserves manual structure
- supports citations and page provenance
- stays compatible with hierarchical hybrid retrieval later

## Recommendation

Recommendation: `Section-aware child chunking with parent lineage`.

What this means:

- treat each manual section as a parent unit
- split long sections into smaller child chunks for retrieval
- keep each child chunk linked to its parent section
- preserve heading path and page span for every child chunk

This is the best default for this project because it balances retrieval quality, interpretability, and future extensibility.

## Overlap Policy

Recommendation: `Keep overlap modest`.

Why:

- overlap helps preserve context across chunk boundaries
- too much overlap creates duplicate candidates and noisier ranking
- hybrid retrieval and reranking usually work better when chunks are distinct enough

Suggested v1 approach:

- use small overlap only when splitting long prose
- prefer structural boundaries over arbitrary overlap
- do not overlap across section boundaries

In practice, overlap should be a supporting mechanism, not the main way context is preserved.

## Should We Use Semantic Chunking?

Recommendation: `Not as the primary chunking strategy in v1`.

Why:

- semantic chunking can produce more coherent chunks than pure fixed-size splitting
- but embedding-driven or model-driven chunk boundaries are harder to inspect and reproduce
- for manuals, section headings, warnings, procedures, and tables already provide strong natural boundaries

Recommended position:

- use document structure first
- use semantic cues inside a section when deciding where to split long content
- defer fully semantic chunking until we have a baseline and evaluation data

So the answer is `yes, semantic signals are useful`, but `no, full semantic chunking should not be the primary strategy yet`.

## Chunking Strategies Considered

### 1. Fixed-size token chunking

Description:

- split text by token or character count with overlap

Pros:

- easy to implement
- easy to scale
- predictable chunk sizes

Cons:

- can cut procedures or warnings in awkward places
- ignores document structure
- weak fit for citation quality

Recommendation: `No` as the main strategy.

### 2. Page-based chunking

Description:

- treat each page as a chunk

Pros:

- very simple
- page citations are direct

Cons:

- pages are poor semantic boundaries
- one page may contain several unrelated topics
- a procedure may span multiple pages

Recommendation: `No` as the main strategy.

### 3. Section-based chunking without child chunks

Description:

- use whole sections as retrieval chunks

Pros:

- preserves structure well
- easy to map to headings and TOC

Cons:

- some sections will be too large for retrieval and reranking
- can dilute relevance for precise troubleshooting questions

Recommendation: `No` as the only strategy.

### 4. Section-aware child chunking

Description:

- keep section structure as the parent
- create smaller retrieval chunks inside each section

Pros:

- preserves manual structure
- improves retrieval precision
- keeps lineage for later hierarchical retrieval
- easier to debug than black-box semantic chunking

Cons:

- requires more ingestion logic
- needs good section detection

Recommendation: `Yes`, this is the primary strategy.

### 5. Fully semantic chunking

Description:

- split content based on semantic similarity shifts or model-based segment boundaries

Pros:

- can produce coherent units in messy text
- can outperform naive fixed-size chunking in some corpora

Cons:

- less deterministic
- harder to inspect and tune
- may not add much value when manuals already have strong structure

Recommendation: `Maybe later`, after baseline evaluation.

### 6. Parent-child hierarchical chunking

Description:

- store larger parent units and smaller child units together
- retrieve children while retaining parent context

Pros:

- strong fit for hierarchical hybrid retrieval
- supports precise retrieval with broader context available
- aligns well with section-heavy manuals

Cons:

- more complex than flat chunking
- needs careful metadata and retrieval design

Recommendation: `Design for it now, compare it later`.

## Recommended v1 Chunking Rules

- use headings and section boundaries whenever available
- use TOC as a structural hint, not a single source of truth
- keep one coherent procedure, warning block, or explanation together where possible
- split oversized sections into child chunks for retrieval
- keep table content chunkable and traceable
- keep figure references attached to nearby explanatory text when useful
- preserve parent section id, heading path, and page span on every chunk

## How Tables And Special Content Affect Chunking

Tables:

- should be treated as first-class content units
- may become dedicated chunks when they answer questions directly
- should also have a searchable text rendering

Warnings and cautions:

- should stay intact whenever possible
- should not be split across arbitrary chunk boundaries

Procedures:

- step sequences should be preserved as coherent units when feasible
- if long, split between logical step groups instead of pure size cutoffs

## What We Are Deferring

Defer these until we have baseline measurements:

- fully semantic chunking as the default
- query-adaptive chunking
- LLM-generated chunk summaries during ingestion
- multimodal chunking centered on diagrams

## Chosen Path

The recommended path is:

1. Start with section-aware child chunking.
2. Preserve parent-child lineage from day one.
3. Use structure first and semantic cues second.
4. Keep overlap small and intentional.
5. Compare this later against a more hierarchical retrieval strategy on the same evaluation set.
