-- Airflow metadata and assignment data are intentionally separated.
CREATE DATABASE airflow;
\connect earthquake

CREATE TABLE IF NOT EXISTS earthquake_events (
    event_uid TEXT PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    depth_km DOUBLE PRECISION CHECK (depth_km >= 0),
    magnitude DOUBLE PRECISION CHECK (magnitude BETWEEN -2 AND 10),
    magnitude_type TEXT,
    place TEXT,
    province TEXT NOT NULL,
    is_in_thailand BOOLEAN NOT NULL,
    sources TEXT[] NOT NULL,
    source_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_score DOUBLE PRECISION NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_time ON earthquake_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_mag ON earthquake_events (magnitude);
CREATE INDEX IF NOT EXISTS idx_events_sources ON earthquake_events USING GIN (sources);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    source_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_count INTEGER NOT NULL DEFAULT 0,
    valid_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    upserted_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS rejected_events (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    source TEXT,
    reason TEXT NOT NULL,
    payload JSONB NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

