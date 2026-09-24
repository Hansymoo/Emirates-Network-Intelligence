-- Raw layer: data as received, no cleaning.

-- One row per flight object returned by OpenSky. The API row is kept as JSONB.
CREATE TABLE IF NOT EXISTS raw.opensky_flights (
    raw_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_airport   TEXT NOT NULL,
    query_direction TEXT NOT NULL CHECK (query_direction IN ('departure', 'arrival')),
    query_date      DATE NOT NULL,
    payload         JSONB NOT NULL,
    run_id          BIGINT REFERENCES ops.pipeline_run (run_id),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_raw_opensky_flights_query
    ON raw.opensky_flights (query_airport, query_direction, query_date);

-- OpenSky aircraft metadata (selected columns only).
CREATE TABLE IF NOT EXISTS raw.aircraft_registry (
    icao24           TEXT,
    registration     TEXT,
    manufacturericao TEXT,
    manufacturername TEXT,
    model            TEXT,
    typecode         TEXT,
    operator         TEXT,
    operatoricao     TEXT,
    built            TEXT,
    engines          TEXT,
    run_id           BIGINT REFERENCES ops.pipeline_run (run_id),
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_raw_aircraft_registry_icao24
    ON raw.aircraft_registry (icao24);

-- OurAirports reference data (selected columns only).
CREATE TABLE IF NOT EXISTS raw.airports (
    ident         TEXT,
    type          TEXT,
    name          TEXT,
    latitude_deg  DOUBLE PRECISION,
    longitude_deg DOUBLE PRECISION,
    iso_country   TEXT,
    municipality  TEXT,
    icao_code     TEXT,
    iata_code     TEXT,
    run_id        BIGINT REFERENCES ops.pipeline_run (run_id),
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);