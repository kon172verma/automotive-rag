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

Recommendation: `Parent-child hierarchical chunking with semantic splitting inside oversized units`.

What this means:

- treat each manual section as a parent unit
- create child chunks inside each parent for retrieval
- if a child is still too large, split it semantically inside that same parent
- never let semantic splitting cross parent boundaries
- preserve heading path and page span for every child chunk

This is the best default for this project because it keeps the manual's real structure while still giving us flexibility when a section is too large or too mixed.

## Overlap Policy

Recommendation: `Prefer zero overlap; use small overlap only as a fallback`.

Why:

- overlap helps preserve context across chunk boundaries
- too much overlap creates duplicate candidates and noisier ranking
- parent-child hierarchy already preserves broader context through the parent
- sibling relationships already preserve local neighborhood context
- hybrid retrieval and reranking usually work better when chunks are distinct enough

Suggested v1 approach:

- use no overlap when splitting at a clean structural or semantic boundary
- use small overlap only when splitting long prose with weak internal boundaries
- prefer structural boundaries over arbitrary overlap
- do not overlap across section boundaries

In practice, overlap should be a fallback mechanism, not the main way context is preserved.

## Should We Use Semantic Chunking?

Recommendation: `Yes, but only inside the hierarchical structure`.

Why:

- semantic chunking can produce more coherent chunks than pure fixed-size splitting
- manuals already have strong structural boundaries, so semantic chunking should refine structure rather than replace it
- this keeps the system more inspectable than fully semantic chunking everywhere

Recommended position:

- use document structure first
- use semantic cues inside a parent when deciding where to split oversized content
- do not use semantic chunking across unrelated sections
- defer fully semantic chunking as a standalone default until we have evaluation data

So the answer is `yes, semantic splitting is part of the plan`, but it should operate inside a parent-child hierarchy rather than replace it.

## Parent-Child Strategy

Recommendation: `Use parent-child hierarchy as the primary chunk model`.

Parent units:

- document sections
- subsection blocks when the manual clearly provides them
- table or procedure containers when they behave like standalone units

Child units:

- retrieval-sized chunks inside a parent
- semantically split only when the initial child would be too large

This gives us:

- faithful structure from the manual
- better retrieval precision than whole-section chunks
- a clean path to hierarchical hybrid retrieval later

Why overlap is usually unnecessary here:

- parent sections preserve broader context
- sibling ordering preserves local neighborhood context
- semantic splits aim to break at meaningful boundaries rather than arbitrary token counts

If additional context is needed later, retrieval-time expansion to adjacent siblings is usually cleaner than duplicating text across stored chunks.

## How Do We Know If A Chunk Has Siblings?

Recommendation: store sibling relationships explicitly in metadata.

Useful fields:

- `parent_section_id`
- `chunk_index_within_parent`
- `sibling_count`
- `prev_chunk_id` when present
- `next_chunk_id` when present

This makes it easy to know:

- whether a chunk is the only child in a parent
- whether adjacent chunks should be expanded for context
- how to reconstruct the local neighborhood around a retrieved chunk

The simplest rule is:

- if two chunks share the same `parent_section_id`, they are siblings
- `chunk_index_within_parent` gives their order

## Chunk Size Guidance

Recommendation: use a target size plus a hard ceiling.

Suggested v1 values:

- target child chunk size: `300-500 tokens`
- preferred soft ceiling: `650 tokens`
- hard ceiling: `800 tokens`

Why this range:

- it is large enough to preserve short procedures and warnings
- it is small enough to keep retrieval specific
- it leaves room for multiple chunks in the final LLM context window

Exceptions:

- do not split small tables just to hit the target size
- do not break short warning blocks or tightly coupled step sequences unnecessarily
- if a large procedure must be split, split by logical step groups

So the policy is not "everything must be the same size." It is "keep chunks coherent, but keep them under a reasonable upper bound."

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

Recommendation: `Yes`, but now folded into the parent-child primary design.

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

Recommendation: `No` as the primary strategy.

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

Recommendation: `Yes`, this is the primary structure.

## Recommended v1 Chunking Rules

- use headings and section boundaries whenever available
- use TOC as a structural hint, not a single source of truth
- keep one coherent procedure, warning block, or explanation together where possible
- create children inside each parent section
- if a child is too large, split it semantically inside that same parent
- keep table content chunkable and traceable
- keep figure references attached to nearby explanatory text when useful
- preserve parent section id, heading path, page span, and sibling order on every chunk

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

- query-adaptive chunking
- LLM-generated chunk summaries during ingestion
- multimodal chunking centered on diagrams

## Chosen Path

The recommended path is:

1. Start with parent-child hierarchical chunking.
2. Preserve parent-child lineage and sibling order from day one.
3. Use structure first and semantic splitting second.
4. Keep overlap small and intentional.
5. Compare this later against alternative chunking variants on the same evaluation set.
