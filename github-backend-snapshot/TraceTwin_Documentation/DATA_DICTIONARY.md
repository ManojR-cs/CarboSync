# Data Dictionary & Entity Specifications — TraceTwin

**Document Type:** Conceptual Data Dictionary & Attribute Specifications  
**Current Stage:** Architecture & Design (Proposed for Hackathon Implementation)  
**Last Updated:** October 16, 2026
**Compliance Standard:** Strict Data Minimization (Zero Student PII in Database)  

## Current B3 Persistence Boundary

The backend persists assessment IDs and creation times, plus commute calculation records. The SQLite tables remain `assessments` and `commute_calculations`; validated request JSON and result JSON are saved as snapshots linked by a foreign key. New B3 snapshots include per-input activity provenance, the candidate factor snapshot or approved registry snapshot, calculation mode, method version, status, and metadata availability. The default file is repository-root `carbosync.db`; `CARBOSYNC_DATABASE_PATH` may select another file. No student-level personal information is collected or persisted.

This is the implemented B3 persistence subset, not an implementation of every conceptual entity below. The current request contract remains in `BACKEND.md` Section 6. Legacy B2 JSON snapshots are unchanged; retrieval adds an explicit unavailable-metadata indicator only to the response. Parking observations, detection corrections, scenario records, and recommendations are not persisted.

---

## 1. Data Governance & Privacy Architecture

TraceTwin enforces strict privacy-by-design principles:
1. **Zero Student Personal Data:** No student names, roll numbers, individual attendance timestamps, biometric identifiers, or residential street addresses are stored in the database.
2. **Locality Minimization:** Geographic origins are restricted to coarse locality, ward, or postal code identifiers.
3. **Evidence Tagging:** New B3 commute calculations store separate provenance for daily vehicle counts, one-way distance, and annual days. Provenance completeness does not establish factual accuracy or representativeness. Candidate factor metadata remains unapproved unless the server resolves a factor from the owner-approved registry.

---

## 2. Entity: `Assessment`
Represents an institutional carbon accounting session, specifying the audit boundaries, academic period, and physical campus location.

> **Contract boundary:** This proposed entity's `annual_days` default is not used by the current API. The B1 request requires `annual_days` explicitly and does not apply a default; see `BACKEND.md` Section 6.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `assessment_id` | Unique identifier for the audit session. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^ast_[a-zA-Z0-9_-]{8,32}$` |
| `name` | Human-readable title of the audit. | String | — | `[Assumption]` | Yes | Non-sensitive | Length: 3–100 characters. |
| `campus_area` | Target campus facility or parking gate. | String | — | `[Direct observation]` | Yes | Non-sensitive | Non-empty string (e.g., "North Gate Parking"). |
| `reporting_period`| Timeframe covered by the assessment. | String | — | `[Assumption]` | Yes | Non-sensitive | E.g., "Academic Year 2026-27". |
| `annual_days` | Number of active campus operating days. | Integer | days/year | `[Source-derived value]` | Yes | Non-sensitive | Integer $\ge 1$ and $\le 366$ (Default: 200). |
| `created_at` | Timestamp of assessment initialization. | Timestamp | ISO 8601 | `[Direct observation]` | Yes | Non-sensitive | Valid UTC/IST timestamp string. |

---

## 3. Entity: `ParkingObservation`
Represents a physical photographic snapshot taken at a campus parking facility at a specific point in time.

> [!WARNING]
> **Methodology Boundary:** A `ParkingObservation` is a static snapshot of parked vehicles at a single instant. It **does not** represent the total daily unique commuters and **must never** be summed with daily commute survey totals.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `observation_id` | Unique identifier for the photo audit. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^obs_[a-zA-Z0-9_-]{8,32}$` |
| `assessment_id` | Foreign key referencing parent Assessment. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `assessment_id`. |
| `image_file_path`| Local storage path to the uploaded image. | String | — | `[Direct observation]` | Yes | Non-sensitive | Must reside in volatile uploads directory. |
| `capture_time` | Date and time photograph was captured. | Timestamp | ISO 8601 | `[Direct observation]` | Yes | Non-sensitive | Valid timestamp; cannot be in future. |
| `parking_lot_name`| Name/identifier of the specific lot. | String | — | `[Direct observation]` | Yes | Non-sensitive | E.g., "Two-Wheeler Enclosure Block B". |
| `weather_tag` | Weather conditions during capture. | String (Enum) | — | `[Direct observation]` | No | Non-sensitive | Enum: `Clear`, `Rain`, `Overcast`. |
| `verification_state`| State of human review loop. | String (Enum) | — | `[Human-confirmed observation]` | Yes | Non-sensitive | Enum: `Pending`, `Confirmed`, `Rejected`. |

---

## 4. Entity: `DetectionAndCorrection`
Represents individual bounding-box vehicle detections extracted by the computer vision model and subsequently audited by a human reviewer.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `detection_id` | Unique identifier for the bounding box. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^det_[a-zA-Z0-9_-]{8,32}$` |
| `observation_id` | Foreign key referencing parent Observation.| String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `observation_id`. |
| `raw_class` | Category detected by YOLO11n. | String | — | `[Direct observation]` | Yes | Non-sensitive | E.g., "bicycle", "car", "motorcycle", "bus", "truck". |
| `raw_confidence` | Model confidence score. | Float | ratio | `[Direct observation]` | Yes | Non-sensitive | Real number $\in [0.00, 1.00]$. |
| `verified_category`| Human-confirmed vehicle category. | String (Enum) | — | `[Human-confirmed observation]` | Yes | Non-sensitive | Enum: `Cars`, `Motorcycles and scooters`, `Buses and campus shuttles`, `Other fuel-burning vehicles`. |
| `box_coordinates`| Bounding rectangle $[x_{min}, y_{min}, x_{max}, y_{max}]$. | Object (JSON) | pixels | `[Human-confirmed observation]` | Yes | Non-sensitive | Coordinates within image dimensions: $0 \le x \le W$, $0 \le y \le H$. |
| `is_deleted` | Flag indicating deletion by reviewer. | Boolean | — | `[Human-confirmed observation]` | Yes | Non-sensitive | Default: `false`. |
| `is_manually_added`| Flag indicating vehicle added by human. | Boolean | — | `[Human-confirmed observation]` | Yes | Non-sensitive | Default: `false`. |

---

## 5. Entity: `AggregateCommuteInput`
Represents modal activity parameters used by the deterministic carbon engine to compute baseline emissions.

> **Contract boundary:** This is a conceptual entity. The live API shape is defined only in `BACKEND.md` Section 6. B3 implements per-input provenance, but does not implement `source_stream`, survey import, or the other proposed entity fields below.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `input_id` | Unique identifier for the commute record. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^inp_[a-zA-Z0-9_-]{8,32}$` |
| `assessment_id` | Foreign key referencing parent Assessment. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `assessment_id`. |
| `vehicle_category`| Standardized vehicle class. | String (Enum) | — | `[Assumption]` | Yes | Non-sensitive | Enum: `Cars`, `Motorcycles and scooters`, `Buses and campus shuttles`, `Other fuel-burning vehicles`. |
| `daily_vehicle_count`| Estimated commuting vehicles in class. | Float | vehicles/day | `[Survey-reported value]` | Yes | Non-sensitive | Value $\ge 0.0$. |
| `avg_one_way_distance`| Average road commute distance. | Float | km | `[Survey-reported value]` | Yes | Non-sensitive | Value $> 0.0$ and $\le 120.0$ km. |
| `vehicle_occupancy`| Average number of persons per vehicle. | Float | persons/veh | `[Survey-reported value]` | Yes | Non-sensitive | Value $\ge 1.0$ (e.g., Car: 1.15, Bus: 35.0). |
| `sample_size` | Number of survey responses supporting input. | Integer | count | `[Survey-reported value]` | Yes | Non-sensitive | Integer $\ge 1$. If $< 20$, UI warning is triggered. |
| `source_stream` | Provenance stream of the input data. | String (Enum) | — | `[Source-derived value]` | Yes | Non-sensitive | Enum: `SurveySample`, `InstitutionalRegister`, `SynthesizedScenario`. |

---

## 6. Entity: `RouteDistanceEstimate`
Represents an estimated road-route transit distance between an origin locality and the university campus.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `route_id` | Unique identifier for the route record. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^rte_[a-zA-Z0-9_-]{8,32}$` |
| `origin_locality`| Coarse neighborhood, ward, or pincode. | String | — | `[Survey-reported value]` | Yes | Aggregated Geographic | Locality name (e.g., "Kengeri Satellite Town"). Prohibit street/house numbers. |
| `destination_campus`| University destination campus name. | String | — | `[Assumption]` | Yes | Non-sensitive | E.g., "DSU Main Campus, Kudlu Gate". |
| `road_distance_km`| Driving route distance estimated via GIS. | Float | km | `[Derived calculation]` | Yes | Non-sensitive | Value $> 0.0$ and $\le 150.0$ km. |
| `routing_provider`| GIS service or formula used for routing. | String (Enum) | — | `[Source-derived value]` | Yes | Non-sensitive | Enum: `OSRM_Local`, `GoogleMaps_Centroid`, `ManualLookupTable`. |

---

## 7. Entity: `EmissionFactor` (registry concept)
The B3 server-controlled registry represents factors as immutable versions. Its approved registry is currently empty. Candidate request factors are snapshots, not approved registry records. No factor is independently authenticated by the application.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `factor_id` | Standard identifier for the factor. | String | — | `[Source-derived value]` | Yes | Non-sensitive | Regex: `^EF_[A-Z0-9_]{4,20}$` |
| `vehicle_category`| Target vehicle class. | String (Enum) | — | `[Source-derived value]` | Yes | Non-sensitive | One of the 4 approved categories. |
| `factor_value` | Numerical emission rate. | Float | kg CO2/veh-km | `[Source-derived value]` | Yes | Non-sensitive | Value $> 0.0$ and $\le 2.0$. |
| `metric_scope` | Emission scope boundary. | String (Enum) | — | `[Source-derived value]` | Yes | Non-sensitive | Live B3 calculation supports `Tailpipe_CO2` only; CO2e and lifecycle factors are not accepted. |
| `geographic_scope`| Country / region of source data. | String | — | `[Source-derived value]` | Yes | Non-sensitive | E.g., "India (National)", "Urban Karnataka". |
| `source_title` | Official publication title. | String | — | `[Source-derived value]` | Yes | Non-sensitive | E.g., "India GHG Program / ARAI Road Factors". |
| `source_url` | Web URL to verified source publication. | String (URL) | — | `[Source-derived value]` | No | Non-sensitive | Valid HTTP/HTTPS URL format. |
| `version_year` | Publication or update year. | Integer or null | year | `[Source-derived value]` | Conditional | Non-sensitive | Recorded when available; does not itself establish approval. |
| `approximation_notes`| Disclosures on engine mix / proxy limits. | String | — | `[Assumption]` | Yes | Non-sensitive | Free-text disclosure of limitations. |
| `version` | Immutable factor version identifier. | String | — | `[Source-derived value]` | Yes | Non-sensitive | A changed factor is a new version; historical snapshots retain the exact value and metadata used. |
| `approval_status` | Registry governance state. | Enum | — | — | Yes | Non-sensitive | `candidate`, `approved`, or `retired`; request data cannot set this status. |
| `review_evidence` / `owner_approval_decision` | Evidence and explicit owner decision for approval. | String or null | — | — | Required for approved | Non-sensitive | No approved factor exists until these are recorded by an explicit owner decision. |

---

## 8. Entity: `CalculationRun` (Baseline)
Represents a deterministic calculation of annual campus commute emissions based on active commute inputs and emission factors.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `run_id` | Unique identifier for calculation execution.| String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^run_[a-zA-Z0-9_-]{8,32}$` |
| `assessment_id` | Foreign key referencing parent Assessment. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `assessment_id`. |
| `annual_vkt_total`| Total annual vehicle-kilometres traveled. | Float | km/year | `[Derived calculation]` | Yes | Non-sensitive | Value $\ge 0.0$. |
| `annual_kg_co2` | Total annual emissions in kilograms. | Float | kg CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Value $\ge 0.0$. |
| `annual_tonnes_co2`| Total annual emissions in metric tonnes. | Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Formula: `annual_kg_co2 / 1000.0`. |
| `category_breakdown`| JSON object containing per-category totals. | Object (JSON) | mixed | `[Derived calculation]` | Yes | Non-sensitive | JSON mapping 4 categories to VKT and $t CO_2$. |
| `is_campus_projection`| Flag indicating sample extrapolation. | Boolean | — | `[Assumption]` | Yes | Non-sensitive | `false` = Sample Baseline; `true` = Projected Total. |

---

## 9. Entity: `DigitalTwinScenario`
Represents an intervention simulation, modeling the carbon impact of campus operational or transit policy changes.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `scenario_id` | Unique identifier for the scenario run. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Regex: `^scen_[a-zA-Z0-9_-]{8,32}$` |
| `run_id` | Foreign key referencing baseline run. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `run_id`. |
| `scenario_type` | Approved intervention archetype. | String (Enum) | — | `[Assumption]` | Yes | Non-sensitive | Enum: `FewerCommuteDays`, `Carpooling`, `BusShuttleIntervention`. |
| `parameters_json`| Configuration parameters applied. | Object (JSON) | mixed | `[Assumption]` | Yes | Non-sensitive | Valid JSON with scenario-specific bounds. |
| `scenario_tonnes_co2`| Forecasted annual emissions under policy. | Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Real number $\ge 0.0$. |
| `avoided_tonnes_co2`| Gross emissions avoided from private travel. | Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Value $\ge 0.0$. |
| `added_tonnes_co2`| Added emissions from new transit (e.g. bus).| Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Value $\ge 0.0$ (Critical for Shuttle scenario). |
| `net_savings_tonnes_co2`| Net avoided emissions ($Avoided - Added$). | Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Formula: `avoided_tonnes_co2 - added_tonnes_co2`. Can be negative. |

---

## 10. Entity: `AIRecommendation`
Represents a qualitative policy recommendation generated by the Guarded AI Proxy or the Deterministic Fallback Engine.

| Field Name | Description / Meaning | Conceptual Type | Unit | Evidence Label | Req? | Privacy Class | Validation Rule |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `rec_id` | Recommendation identifier from catalog. | String (Enum) | — | `[Source-derived value]` | Yes | Non-sensitive | Must match an approved institutional ID (e.g., `REC_POOL_01`). |
| `scenario_id` | Foreign key referencing parent scenario. | String (UUID) | — | `[Derived calculation]` | Yes | Non-sensitive | Must match active `scenario_id`. |
| `title` | Policy recommendation headline. | String | — | `[Assumption]` | Yes | Non-sensitive | Length: 5–80 characters. |
| `qualitative_rationale`| Contextual narrative explanation. | String | — | `[Assumption]` | Yes | Non-sensitive | Length: 20–500 characters. Prohibit numerical claims. |
| `attached_net_savings`| Savings figure attached by deterministic engine.| Float | tonnes CO2/year | `[Derived calculation]` | Yes | Non-sensitive | Injected exclusively by deterministic engine. |
| `implementation_difficulty`| Policy execution barrier. | String (Enum) | — | `[Assumption]` | Yes | Non-sensitive | Enum: `Low`, `Medium`, `High`. |
| `fallback_flag` | Indicates whether deterministic fallback fired.| Boolean | — | `[Direct observation]` | Yes | Non-sensitive | `true` if AI failed/timed out; `false` if AI succeeded. |
| `fallback_label` | Transparency label displayed to user. | String | — | `[Direct observation]` | Yes | Non-sensitive | Value: `"Rule-based plan (AI unavailable)"` if `fallback_flag` is true. |
## Implemented Demo Snapshot Entities

The demo API adds a SQLite demo_analyses record containing analysis_id, created_at, detections_json, assumptions_json, and result_json. These are structured aggregate demo values; no image bytes, filesystem paths, student identifiers, or LLM credentials are stored.

The detection snapshot contains per-class counts, motor-vehicle and bicycle totals, model name, configured confidence, and snapshot scope. The assumptions snapshot preserves annual operating days, each class's trip-cycle and distance assumptions with descriptions, per-category illustrative factor ID/value/unit/geography/source/applicability/limitations, and the three scenario settings. Results preserve the deterministic baseline and scenario calculations, factor snapshots with backend-assigned content hashes, computed best scenario, limitations, and recommendation/fallback status.

Demo factor status is always backend-assigned illustrative_unapproved. Demo records are not approved registry records. The separately implemented B3 assessment and commute tables/contracts are unchanged.
