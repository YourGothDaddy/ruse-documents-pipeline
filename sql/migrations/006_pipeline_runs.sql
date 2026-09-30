CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'running',
    documents_processed INTEGER,
    documents_new INTEGER,
    error_message TEXT
);
