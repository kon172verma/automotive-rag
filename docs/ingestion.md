# Ingestion

This document records the recommended decisions for ingesting automotive manuals into a retrieval-ready corpus.

## Goal

Turn raw manufacturer PDFs into structured, traceable, searchable records that support:

- hybrid retrieval now
- hierarchical hybrid retrieval later
- citation-friendly answer generation
- repeatable re-ingestion as the corpus grows

## Recommended Ingestion Strategy

Use a structured PDF extraction pipeline that preserves document hierarchy, tables, page provenance, and optional image references.

Recommendation:

- primary extraction tool: `Docling`
- fallback/debug tool: `PyMuPDF`
- store both document-level and chunk-level records
- preserve section lineage so hierarchical retrieval remains possible later

## Key Questions

### 1. What PDF extraction tool should we use?

Recommendation: `Docling` as the primary extractor.

Why:

- it produces a structured document representation rather than plain text only
- it supports text, tables, pictures, provenance, and document hierarchy
- it fits the long-term need for page-aware and section-aware chunking

Use `PyMuPDF` as a secondary tool for:

- fast debugging
- extraction sanity checks
- custom page-level fixes if needed

Do not optimize for the simplest text dump. Optimize for future structure retention.

### 2. Should OCR be used by default?

Recommendation: `Conditional`.

Why:

- born-digital manuals should not need aggressive OCR
- OCR can introduce noise when the PDF already has clean text
- some scanned or image-heavy pages may still need OCR

Recommended policy:

- try native text extraction first
- enable OCR only when text is missing or unusable
- record in metadata whether OCR was used

### 3. How should we chunk the manuals?

Recommendation: see [chunking.md](/Users/konark/Desktop/Personal/automotive-rag/docs/chunking.md).

Short answer:

- use parent-child hierarchical chunking
- use semantic splitting only when a child chunk is still too large
- keep overlap modest
- preserve section and page provenance
- make the chunk format compatible with future hierarchical retrieval

Chunking is important enough to keep as a separate design file.

### 4. Should the metadata be future-compatible with hierarchical RAG?

Recommendation: `Yes`.

Why:

- changing metadata shape later is avoidable churn
- parent-child lineage is cheap to preserve now
- hierarchy is likely useful for manuals with rich sectioning

Minimum structure to preserve:

- document
- section
- chunk

Each chunk should know its:

- document id
- parent section id
- chunk id
- sibling order
- sibling count
- page span
- heading path
- source text location

### 5. What should the metadata look like?

Recommendation: keep both document-level and chunk-level metadata.

Document-level fields:

- `doc_id`
- `make`
- `model`
- `year`
- `trim` when known
- `manual_type`
- `source_file`
- `source_hash`
- `language`
- `ingestion_version`
- `ingested_at`

Section-level fields:

- `section_id`
- `doc_id`
- `section_title`
- `section_path`
- `section_level`
- `toc_label` when available
- `page_start`
- `page_end`
- `parent_section_id` when nested

Chunk-level fields:

- `chunk_id`
- `doc_id`
- `section_id`
- `chunk_index`
- `chunk_index_within_parent`
- `sibling_count`
- `prev_chunk_id`
- `next_chunk_id`
- `chunk_text`
- `embedding_text`
- `chunk_text_for_keyword_search`
- `page_start`
- `page_end`
- `heading_path`
- `content_type`
- `contains_table`
- `contains_image_ref`
- `ocr_used`
- `char_count`
- `token_count_estimate`

Notes:

- `chunk_text` is the canonical chunk content
- `embedding_text` is the text actually sent to the embedding model
- `chunk_text_for_keyword_search` can include search-friendly normalization or table renderings

Recommended `content_type` examples:

- `procedure`
- `warning`
- `maintenance_schedule`
- `specification`
- `table`
- `overview`

This metadata shape should work for both current hybrid retrieval and later hierarchical retrieval.

### 5A. What gets embedded?

Recommendation: embed `content-centric text`, not the full metadata blob.

Embed:

- chunk content
- useful heading context
- table text renderings when relevant

Do not embed directly:

- ids
- timestamps
- ingestion bookkeeping
- most filter metadata such as `doc_id`, `year`, or `manual_type`

The practical pattern should be:

- keep structured metadata in columns or fields for filtering
- build an `embedding_text` field from the chunk content plus selected heading context

### 5B. What format should chunks be stored in?

Recommendation: store chunks as structured records, not just raw JSON blobs.

Recommended storage shape:

- one row per chunk in the main datastore
- explicit columns for key metadata and text fields
- vector column for embeddings
- optional `jsonb` or raw-structure field for extractor output or extra attributes

Why:

- easier filtering and querying
- easier joins with sections and documents
- easier debugging than opaque JSON-only storage

JSON is still useful as a secondary representation, but it should not be the only format.

### 6. What should we do with tables?

Recommendation: `Extract them as first-class structured content`.

Why:

- maintenance schedules and specifications often live in tables
- flattening them into plain paragraphs loses important structure
- users may ask table-like questions directly

Recommended handling:

- preserve structured table output when the extractor provides it
- create searchable text renderings of tables for hybrid retrieval
- store table metadata and provenance separately
- let chunks reference the table asset or structured table record

For v1, table text should be retrievable even if richer table reasoning comes later.

### 7. What should we do with images or diagrams?

Recommendation: `Preserve references, but do not make image understanding central in v1`.

Why:

- some diagrams are useful, but most early QA value will come from text and tables
- image understanding adds another layer of complexity
- we still want traceability for future upgrades

Recommended handling:

- keep image references and page provenance
- store captions and nearby explanatory text when available
- mark chunks that reference figures
- defer full multimodal retrieval and visual reasoning

If critical instructions appear only inside images, we can revisit OCR or multimodal handling later.

### 8. Should we use the table of contents now?

Recommendation: `Yes, in a lightweight way`.

Why:

- the TOC is a strong document navigation signal
- it can help section labeling and chunk lineage
- it supports later hierarchical retrieval without forcing a complex design now

Recommended use in v1:

- use TOC entries as candidate section boundaries or labels
- map chunks to the nearest heading path when reliable
- store TOC-derived section metadata separately from chunk text

Do not make the whole pipeline depend on perfect TOC parsing. Use it as a helpful structural guide, not a brittle single point of failure.

### 9. How should ingestion handle versioning and re-runs?

Recommendation: `Make ingestion idempotent and traceable`.

Why:

- manuals will grow over time
- chunking logic will evolve
- we need to compare retrieval quality across ingestion versions

Recommended controls:

- hash the source file
- version the ingestion pipeline
- version the chunking strategy
- support full re-ingestion of a document without orphan records

### 10. What validation checks should ingestion produce?

Recommendation: `Add lightweight ingestion QA from the start`.

Checks to record:

- page count
- extracted text coverage
- missing-text pages
- number of sections
- number of chunks
- number of tables
- number of image references
- OCR usage

This will make ingestion issues visible before they become retrieval issues.

## Chosen Path

The recommended ingestion path is:

1. Extract PDFs into a structured document format.
2. Preserve headings, sections, page spans, tables, and image references.
3. Create section-aware child chunks with parent lineage.
4. Store metadata that supports both current hybrid and future hierarchical hybrid retrieval.
5. Add ingestion validation and versioning from the beginning.

## References

- Docling: <https://docling-project.github.io/docling/>
- Docling supported formats and chunk export: <https://docling-project.github.io/docling/usage/supported_formats/>
- Docling document hierarchy and structure: <https://github.com/docling-project/docling/blob/main/docs/concepts/docling_document.md>
- PyMuPDF basics and table extraction: <https://pymupdf.readthedocs.io/en/latest/the-basics.html>
- PyMuPDF table extraction FAQ: <https://pymupdf.readthedocs.io/en/latest/faq/index.html>
