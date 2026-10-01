CREATE TABLE tax_rates (
    id SERIAL PRIMARY KEY,
    tax_type TEXT UNIQUE NOT NULL,
    rate NUMERIC(5,2) NOT NULL,
    rate_unit TEXT NOT NULL DEFAULT 'per_mille',
    source_document TEXT NOT NULL,
    last_checked TIMESTAMP NOT NULL DEFAULT NOW()
);