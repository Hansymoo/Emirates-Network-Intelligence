# Data Findings

Independent analysis of public data. Not affiliated with Emirates.

## Finding 1: Regional disruption in 2026 is visible in the Emirates flight data

### What we observed

Source: OpenSky `/flights/departure` for OMDB (Dubai), one UTC calendar day per row.
"Emirates" means callsigns starting with `UAE`. These are single-day probe samples; the
full daily series is loaded in Phase 4 and this table will be replaced by it.

| Date (2026) | All departures at OMDB | Emirates departures | Emirates share |
|---|---|---|---|
| Aug 19-25 (baseline week) | 419-507 | 200-227 | about 44-48% |
| Jun 26 | 435 | 203 | 46.7% |
| Jun 16 | 104 | 70 | 67.3% |
| Apr 27 | 285 | 159 | 55.8% |
| May 27 | 18 | 14 | 77.8% |
| Mar 28 | 50 | 44 | 88.0% |

### Context from public reporting

These are secondary sources (news and travel media). We have not checked them against
primary statements from airlines or airport operators.

- UAE airspace was briefly shut on 17 March 2026 amid Iran-related attacks, with wider
  cancellations across the region: https://www.cnbc.com/2026/03/17/uae-airspace-closure-dubai-airport-drone-strike-middle-east-flights.html
- Dubai and Abu Dhabi airports had reopened by mid-April but were operating reduced
  services: https://www.skyscanner.net/news/flights-disrupted-after-airspace-closures-dubai-doha-abu-dhabi-cancellations
- Disruption "in waves", a reported double-digit Q1 traffic decline at Dubai, restrictions
  lifted in May, and rolling delays into September: https://www.thetraveler.org/uae-flight-disruptions-2026-what-travelers-need-to-know-2/
- Emirates route suspensions for August 2026: https://simpleflying.com/emirates-suspended-routes/

### Interpretation and confidence

The low-volume days are **consistent with** regional disruption. They are **not proven** to be
caused by it.

- **Supports a real operational reduction:** on the low days Emirates' share of all Dubai
  departures rises well above the 44-48% baseline. A receiver outage would reduce all
  airlines about equally and leave the share roughly unchanged.
- **Needs caution:** on May 27 only 18 departures were recorded for all airlines combined.
  Sources we found say national restrictions were lifted in May, so an ADS-B coverage or
  processing gap on that day remains plausible.
- **Alternative explanation we cannot rule out from probes alone:** gaps in OpenSky's
  crowdsourced receiver coverage.

### How the project handles it

- Low-volume days are **not removed**. They are part of the operational history.
- `core.dim_date` carries `is_disrupted_day` and `disruption_note`. Flag windows are defined
  in Phase 6 from cited sources, and each window records its source URL.
- The flag is a contextual annotation, not a causal claim. Dashboards label it as such.
- A data-quality check tracks Emirates' share of OMDB departures per day (Phase 5).

### Limits

- Only flights touching Dubai (OMDB) are captured.
- About 25% of departures have no resolved destination airport.
- Times are ADS-B first/last seen, not scheduled or gate times.