CREATE TABLE IF NOT EXISTS notes (
    id          SERIAL PRIMARY KEY,
    text        TEXT        NOT NULL,
    request_id  UUID        UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
