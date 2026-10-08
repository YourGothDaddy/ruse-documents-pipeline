INSERT INTO topics (name) VALUES
    ('Спорт'),
    ('Обществен ред'),
    ('Местни данъци и такси'),
    ('Други теми')
ON CONFLICT (name) DO NOTHING;