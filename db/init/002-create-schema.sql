CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  make TEXT,
  model TEXT,
  year INTEGER,
  trim TEXT,
  manual_type TEXT NOT NULL,
  language TEXT NOT NULL,
  source_file TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  page_count INTEGER NOT NULL,
  ingestion_version TEXT NOT NULL,
  chunking_strategy TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
  section_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  parent_section_id TEXT REFERENCES sections(section_id) ON DELETE SET NULL,
  section_title TEXT NOT NULL,
  section_path TEXT[] NOT NULL,
  section_level INTEGER NOT NULL,
  toc_label TEXT,
  page_start INTEGER,
  page_end INTEGER
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  section_id TEXT NOT NULL REFERENCES sections(section_id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  chunk_index_within_parent INTEGER NOT NULL,
  sibling_count INTEGER NOT NULL,
  prev_chunk_id TEXT,
  next_chunk_id TEXT,
  page_start INTEGER,
  page_end INTEGER,
  content_type TEXT NOT NULL,
  contains_table BOOLEAN NOT NULL,
  contains_image_ref BOOLEAN NOT NULL,
  ocr_used BOOLEAN NOT NULL,
  char_count INTEGER NOT NULL,
  token_count_estimate INTEGER NOT NULL,
  heading_path TEXT[] NOT NULL,
  chunk_text TEXT NOT NULL,
  chunk_text_for_keyword_search TEXT NOT NULL,
  embedding_text TEXT NOT NULL,
  embedding_text_sha256 TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_dimensions INTEGER NOT NULL,
  embedding VECTOR(1536) NOT NULL,
  search_tsv TSVECTOR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_make_model_year
  ON documents (make, model, year);

CREATE INDEX IF NOT EXISTS idx_sections_doc_id
  ON sections (doc_id);

CREATE INDEX IF NOT EXISTS idx_sections_parent_section_id
  ON sections (parent_section_id);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
  ON chunks (doc_id);

CREATE INDEX IF NOT EXISTS idx_chunks_section_id
  ON chunks (section_id);

CREATE INDEX IF NOT EXISTS idx_chunks_content_type
  ON chunks (content_type);

CREATE INDEX IF NOT EXISTS idx_chunks_search_tsv
  ON chunks USING GIN (search_tsv);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
  ON chunks USING hnsw (embedding vector_cosine_ops);
