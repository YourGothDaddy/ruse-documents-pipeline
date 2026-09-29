CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE document_topics (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, topic_id)
);

CREATE TABLE document_law_references (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    law_code TEXT NOT NULL,
    PRIMARY KEY (document_id, law_code)
);

INSERT INTO topics (name) VALUES
    ('Устройство на територията'),
    ('Общинска собственост'),
    ('Бюджет и финанси'),
    ('Образование'),
    ('Социални дейности'),
    ('Транспорт'),
    ('Околна среда'),
    ('Култура');
