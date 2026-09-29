ALTER TABLE documents DROP CONSTRAINT unique_doc;
ALTER TABLE documents ADD CONSTRAINT unique_detail_url UNIQUE (detail_url);
