ALTER TABLE documents ADD COLUMN full_text_search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(full_text, ''))
    ) STORED;
 
CREATE INDEX idx_documents_full_text_search ON documents USING GIN (full_text_search_vector);