-- Calendar for 2026. Extend the range if the project covers other years.
INSERT INTO core.dim_date (
    date_key, full_date, year, quarter, month, month_name, iso_week,
    day_of_month, day_of_week, day_name, is_weekend
)
SELECT
    to_char(d, 'YYYYMMDD')::INTEGER,
    d::DATE,
    EXTRACT(YEAR FROM d)::SMALLINT,
    EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(MONTH FROM d)::SMALLINT,
    trim(to_char(d, 'Month')),
    EXTRACT(WEEK FROM d)::SMALLINT,
    EXTRACT(DAY FROM d)::SMALLINT,
    EXTRACT(ISODOW FROM d)::SMALLINT,
    trim(to_char(d, 'Day')),
    EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series('2026-01-01'::DATE, '2026-12-31'::DATE, INTERVAL '1 day') AS g(d)
ON CONFLICT (date_key) DO NOTHING;