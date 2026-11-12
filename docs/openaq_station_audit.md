# OpenAQ Station Audit — Lahore

**Lahore Smog Risk Index & Safe-Activity Advisory System**

*This document records findings from a live OpenAQ API query run on Nov 9, 2026, covering all Lahore-area monitoring stations within the city's geographic bounding box. It captures station count, sensor availability, freshness, and the PM10 decision made as a result.*

---

## 1. Summary of Findings

- Total Lahore-area stations found via bounding-box query: **22**
- Stations reporting live today (Nov 9, 2026): **15**
- Stations active within last 7 days: **17**
- Stations excluded from ingestion: **4** (Lahore Clarity, Johar Town, Asst. Commissioner Allama Iqbal, US Diplomatic Post)
- Stations on the allowlist: **18** — all report PM1, PM2.5, particle count, temperature and humidity
- Update frequency: AirGradient network stations update hourly; Clarity station (id 1894641) updates irregularly
- Note: Original estimate was 7 stations — actual count is 22 because most stations use neighborhood names (e.g. 'Gulberg III', 'Model Town') with no 'Lahore' string in the name field. A coordinate-based bounding-box query was required to find them all.

---

## 2. Full Station List

Status legend: LIVE = updated today | ACTIVE = updated within 2 months | SLOW = 1–2 months stale | STALE = 3–10 months stale | DEAD = over 1 year with no updates

| Station Name | ID | Sensors | Last Update | Status |
|---|---|---|---|---|
| Civil Secretariat | 4527035 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Learning Alliance DHA | 4527173 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| HBFC Society, DHA Phase 5 | 4527402 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Sandha Road | 4554729 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Ravi Road | 4555745 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Shalimar Town | 4557686 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| IEEE, Punjab University | 4565933 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Model Town | 4568423 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| College Road | 4605119 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Kahna Hospital | 4609353 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Gulberg III | 4618814 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Cantonment | 4698865 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Pak Arab | 4699919 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Samanabad | 4700982 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Forman Christian College | 4757305 | PM1, PM2.5, RH, Temp, Particle count | Nov 9, 2026 | **LIVE** |
| Barki, Lahore | 4515157 | PM1, PM2.5, RH, Temp, Particle count | Nov 6, 2026 | **LIVE** |
| FOOT & MOUTH DISEASE CENTRE | 4527306 | PM1, PM2.5, RH, Temp, Particle count | Nov 8, 2026 | **LIVE** |
| Lahore (Clarity) | 1894641 | PM1, PM2.5, PM10, Temp (C+F) | Aug 31, 2026 | **ACTIVE** |
| Gajju Matta (Kahna) | 4535267 | PM1, PM2.5, RH, Temp, Particle count | Oct 6, 2026 | **SLOW** |
| Johar Town | 4566427 | PM1, PM2.5, RH, Temp, Particle count | Jan 8, 2026 | **STALE** |
| Asst. Commissioner, Allama Iqbal | 4608421 | PM1, PM2.5, RH, Temp, Particle count | Aug 1, 2025 | **DEAD** |
| US Diplomatic Post | 8664 | PM2.5 only | Mar 4, 2025 | **DEAD** |

---

## 3. The PM10 Problem

### What was found

- 21 of 22 stations (the AirGradient community network) report: PM1, PM2.5, relative humidity, temperature, and particle count — but **no PM10**.
- Only 1 station reports PM10: 'Lahore' (id 1894641, Clarity sensor). Its last reading was Aug 31, 2026 — over 2 months stale at the time of this query.
- Including PM10 as a required model feature would mean either: restricting the entire dataset to 1 station, or introducing 95%+ missing values across all training rows.

### Decision: Exclude PM10 from the model

- PM10 is dropped from the model's feature set entirely. It is not treated as optional or imputed — it is simply not used.
- This was chosen over NaN-imputation and over XGBoost's native missingness handling because the feature has no meaningful signal when it's absent for 95% of rows — including it at all would add schema complexity for no real model benefit.
- PM2.5 is the dominant pollutant in real-world AQI calculations anyway, so removing PM10 does not meaningfully weaken the classifier.
- The Clarity station (id 1894641) is **not ingested** (plan v2): it is stale since Aug 31, 2026 and has no humidity or particle-count sensor, so it cannot provide the full feature set.

---

## 4. Final Feature Set for the Model

Station-level measurements used by the model (all 18 allowlisted stations report every "Yes" item below). The full 23-feature list, including Open-Meteo weather, lag/rolling and calendar features, is in `configs/pipeline_config.yaml`.

| Feature | Available at | Used in model | Note |
|---|---|---|---|
| PM1 | 21/22 stations | **Yes** | Primary pollutant signal |
| PM2.5 | 22/22 stations | **Yes** | Primary signal; dominant in AQI calculation |
| PM10 | 1/22 stations only | **No — excluded** | Only 1 station (Clarity, id 1894641) reports this. Excluded from model to maintain a consistent feature set across all stations. |
| Relative Humidity | 20/22 stations | **Yes** | From OpenAQ stations directly (`station_rh`) |
| Temperature | 22/22 stations | **Yes** | From OpenAQ stations (`station_temp`); Open-Meteo adds city-level weather |
| Wind speed/direction | Open-Meteo only | **Yes** | Fetched from Open-Meteo for Lahore coordinates |
| Particle count (um003) | 20/22 stations | **Yes** | Required feature `particle_count_03` |

---

## 5. Station Allowlist for Module 1.1

The ingestion script (`ingest_openaq.py`) pulls from the 18 "Include" stations only. The allowlist used by code lives in `configs/pipeline_config.yaml` — never hard-code station IDs. A station with no reading in the last 7 days is skipped for that run (warning logged) and used again when it comes back.

| Station | ID | Note |
|---|---|---|
| Civil Secretariat | 4527035 | Include |
| Learning Alliance DHA | 4527173 | Include |
| HBFC Society, DHA Phase 5 | 4527402 | Include |
| Sandha Road | 4554729 | Include |
| Ravi Road | 4555745 | Include |
| Shalimar Town | 4557686 | Include |
| IEEE, Punjab University | 4565933 | Include |
| Model Town | 4568423 | Include |
| College Road | 4605119 | Include |
| Kahna Hospital | 4609353 | Include |
| Gulberg III | 4618814 | Include |
| Cantonment | 4698865 | Include |
| Pak Arab | 4699919 | Include |
| Samanabad | 4700982 | Include |
| Forman Christian College | 4757305 | Include |
| Barki, Lahore | 4515157 | Include |
| FOOT & MOUTH DISEASE CENTRE | 4527306 | Include |
| Gajju Matta (Kahna) | 4535267 | Include — freshness rule applies |
| Lahore (Clarity) | 1894641 | EXCLUDE — stale since Aug 2026, no humidity or particle count |
| Johar Town | 4566427 | EXCLUDE — stale since Jan 2026 |
| Asst. Commissioner, Allama Iqbal | 4608421 | EXCLUDE — stale since Aug 2025 |
| US Diplomatic Post | 8664 | EXCLUDE — dead since Mar 2025, PM2.5 only |

*Verified via live OpenAQ API v3 query on Nov 9, 2026. Station list and sensor availability should be re-verified if significant time elapses before Module 1.1 implementation begins.*
