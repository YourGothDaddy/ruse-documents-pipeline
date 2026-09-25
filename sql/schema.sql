CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE statuses (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    status_id INTEGER REFERENCES statuses(id),
    publish_date DATE,
    file_url TEXT,
    file_type TEXT,
    file_size_kb INTEGER,
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO categories (name) VALUES
    ('Наредби'),
    ('Решения'),
    ('Протоколи'),
    ('Предложения'),
    ('Приватизация');

INSERT INTO statuses (name) VALUES
    ('active'),
    ('repealed'),
    ('unknown');
