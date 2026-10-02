INSERT INTO categories (name) VALUES
    ('Проекто наредби'),
    ('Протоколи от комисии'),
    ('Решения на комисии'),
    ('Отговори'),
    ('Писма'),
    ('Дневен ред'),
    ('Приложения'),
    ('Други')
ON CONFLICT (name) DO NOTHING;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS possibly_incomplete_source BOOLEAN NOT NULL DEFAULT FALSE;