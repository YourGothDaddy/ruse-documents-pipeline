ALTER TABLE documents ADD COLUMN description TEXT;

ALTER TABLE documents ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED;

CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);
