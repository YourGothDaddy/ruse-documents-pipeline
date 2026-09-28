CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS statuses (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    status_id INTEGER REFERENCES statuses(id),
    publish_date DATE,
    file_url TEXT,
    file_type TEXT,
    file_size_kb INTEGER,
    source_url TEXT NOT NULL,
    detail_url TEXT,
    scraped_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_doc UNIQUE (source_url, title)
);

INSERT INTO categories (name) VALUES
    ('Наредби'),
    ('Решения'),
    ('Протоколи'),
    ('Предложения'),
    ('Приватизация')
ON CONFLICT (name) DO NOTHING;

INSERT INTO statuses (name) VALUES
    ('active'),
    ('repealed'),
    ('unknown')
ON CONFLICT (name) DO NOTHING;
