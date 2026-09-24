-- Pipeline monitoring: one row per pipeline execution.
CREATE TABLE IF NOT EXISTS ops.pipeline_run (
    run_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'succeeded', 'failed', 'partial')),
    rows_extracted  INTEGER,
    rows_loaded     INTEGER,
    error_message   TEXT
);

-- One row per source partition (for example OMDB|departure|2026-08-25).
-- Lets the backfill skip finished days and resume after credits run out.
CREATE TABLE IF NOT EXISTS ops.ingestion_log (
    ingestion_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name       TEXT NOT NULL,
    partition_key     TEXT NOT NULL,
    row_count         INTEGER NOT NULL,
    http_status       INTEGER,
    credits_remaining INTEGER,
    run_id            BIGINT REFERENCES ops.pipeline_run (run_id),
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_name, partition_key)
);

-- Results of automated data-quality checks.
CREATE TABLE IF NOT EXISTS ops.dq_check_result (
    result_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id           BIGINT REFERENCES ops.pipeline_run (run_id),
    check_name       TEXT NOT NULL,
    severity         TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    passed           BOOLEAN NOT NULL,
    failed_row_count INTEGER,
    details          JSONB,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);