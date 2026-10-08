ALTER TABLE documents ADD COLUMN IF NOT EXISTS full_text_source TEXT;

UPDATE documents
SET full_text_source = 'detail_page'
WHERE full_text IS NOT NULL
  AND full_text_source IS NULL;