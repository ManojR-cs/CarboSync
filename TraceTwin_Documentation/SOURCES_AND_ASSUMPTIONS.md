# Emission Factor Sources & Operational Assumptions — TraceTwin

**Document Type:** Formal Source Register & Assumptions Benchmark  
**Target Audience:** Environmental Data Analysts, Campus Auditors, Technical Reviewers  
**Last Updated:** October 16, 2026
**Methodological Standard:** Strict separation of tailpipe $CO_2$ from lifecycle/grid factors; documented geographic and fleet limitations.

---

## 1. Candidate Emission Factor Register (Unverified)

The table below compiles candidate values for review. Despite the historical “Verified” wording in this document's earlier title, each listed factor is marked `Needs verification`; none is approved as a production factor by the current backend implementation.

> [!IMPORTANT]
> **Provenance & Unit Disclosure:**
> - All vehicular factors are standardized to **$\text{kg } CO_2/\text{veh-km}$** (Vehicle-Kilometres Traveled).
> - All factors represent **direct tailpipe $CO_2$ emissions** (excluding upstream fuel refining and vehicle manufacturing lifecycle).
> - Factors designated as `Proposed` or `Needs verification` must be finalized during kickoff before calculation freeze.

| Factor ID | Target Category | Specific Fleet / Fuel Proxy | Value & Unit | Scope | Geography | Source Publication & Author | Source URL / Reference | Verification Status | Notes & Known Limitations |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :--- |
| **`EF_CAR_IN_01`** | **Cars** | Mid-size Petrol/Diesel Passenger Car (Fleet Average) | $0.145 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | India (National Urban) | **India GHG Program** (WRI India, TERI, CII) | *India Specific Emission Factors for Road Transport* | `Needs verification` | Reflects mixed Indian car fleet (BS-IV/BS-VI mix). Assumes urban driving cycle; may underestimate stop-and-go Bengaluru traffic congestion. |
| **`EF_CAR_ARAI_02`**| **Cars** | Compact Petrol Hatchback (BS-VI Certified) | $0.132 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | India | **ARAI** (Automotive Research Association of India) | *Emission Factor Development for Indian Vehicles* | `Needs verification` | Laboratory test cycle (Modified Indian Driving Cycle); real-world on-road emissions typically 15–25% higher. |
| **`EF_MOTO_IN_01`** | **Motorcycles and scooters**| 4-Stroke 100–150cc Petrol Two-Wheeler | $0.035 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | India (Urban) | **India GHG Program** | *Road Transport GHG Factor Guidance* | `Needs verification` | Represents modern four-stroke motorcycles. Older two-stroke scooters emit higher unburned hydrocarbons and slightly different $CO_2$ profiles. |
| **`EF_BUS_IN_01`**  | **Buses and campus shuttles**| Standard 40-Seater Diesel Institutional Bus | $0.850 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | India (Urban Transit) | **ARAI / CPCB** (Central Pollution Control Board) | *Air Quality Monitoring & Vehicular Emissions in Urban Cities* | `Needs verification` | Assumes standard diesel fuel consumption of ~3.2 km/litre in urban conditions ($2.68 \text{ kg } CO_2/\text{L} \div 3.2 = 0.838$). |
| **`EF_BUS_DEFRA_02`**| **Buses and campus shuttles**| Local Diesel Transit Bus (Average Load) | $0.980 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | International (UK Benchmark) | **UK DESNZ / DEFRA** (2025/2026 Conversion Factors) | *Government GHG Conversion Factors for Company Reporting* | `Needs verification` | High-quality benchmark, but based on UK transit fleet; provides upper-bound cross-check for Indian institutional shuttles. |
| **`EF_AUTO_IN_01`** | **Other fuel-burning vehicles**| 4-Stroke 3-Wheeler Auto-Rickshaw (CNG / Petrol) | $0.078 \text{ kg } CO_2/\text{veh-km}$ | Tailpipe $CO_2$ | India (Urban) | **TERI / India GHG Program** | *Urban Mobility and Vehicular Emission Inventories* | `Needs verification` | Applied as the default proxy for "Other fuel-burning vehicles". May underestimate light commercial delivery trucks ($~0.220 \text{ kg } CO_2/\text{veh-km}$). |

---

## 2. Critical Analysis of Commonly Misapplied Sources

### 2.1 The Central Electricity Authority (CEA) Grid Factor Fallback Fallacy
- **What it is:** The *CO₂ Baseline Database for the Indian Power Sector*, published annually by the Central Electricity Authority (CEA), Ministry of Power, Government of India.
- **Current Version:** Version 19 / 20 (weighted average grid emission factor: $\approx 0.71\text{--}0.73 \text{ kg } CO_2/\text{kWh}$).
- **Why it is NOT applicable to TraceTwin's baseline:**
  - The CEA factor measures indirect emissions from **grid electricity generation** at central thermal, hydro, and renewable power stations.
  - TraceTwin models **mobile internal combustion engines** burning liquid fossil fuels (petrol, diesel, CNG) directly on the road.
  - Applying CEA electricity factors to road vehicles is a severe category error.
  - *Context:* The CEA factor would only become relevant in a future Phase 2 scenario evaluating on-campus Electric Vehicle (EV) charging stations. For the hackathon MVP, EV modeling is **Out of scope**.

### 2.2 Mixing India GHG Program and UK DEFRA Factors
- The **India GHG Program** factors (jointly published by WRI India, TERI, and CII) are the most geographically authentic sources for domestic fleet dynamics. However, many published tables date from 2015–2018 and reflect pre-BS-VI vehicle distributions.
- **UK DEFRA / DESNZ** factors are updated annually with exceptional statistical precision. However, they reflect Western vehicle masses, stricter fuel sulfur limits, and different ambient driving temperatures.
- **TraceTwin Rule:** India GHG Program and ARAI figures serve as primary benchmarks; DEFRA figures are referenced solely for international cross-validation.

---

## 3. Register of Baseline Operational Assumptions

In environmental modeling, when empirical measurements are unavailable, defensible assumptions must be transparently documented and bounded:

| Parameter ID | Parameter Name | Baseline Default Value | Permitted Range | Evidence Label | Methodological Justification |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **`ASM_DAYS_01`** | **Annual Commuting Days ($Y$)** | $200 \text{ days/year}$ | $150\text{--}240$ | `[Assumption]` | Reflects standard Indian collegiate calendar: two 16-week teaching semesters plus examination periods, excluding gazetted holidays, term breaks, and weekends. |
| **`ASM_OCC_CAR`** | **Baseline Car Occupancy ($O_{\text{car}}$)** | $1.15 \text{ persons/veh}$ | $1.0\text{--}2.0$ | `[Survey-reported value]` | University student/faculty driving is predominantly solo; occasional carpooling with peers or family drop-offs. |
| **`ASM_OCC_MOTO`**| **Baseline Motorcycle Occupancy ($O_{\text{moto}}$)** | $1.05 \text{ persons/veh}$ | $1.0\text{--}1.3$ | `[Survey-reported value]` | Motorized two-wheelers are overwhelmingly ridden solo by university students in urban areas. |
| **`ASM_OCC_BUS`** | **Baseline Campus Shuttle Occupancy ($O_{\text{bus}}$)** | $38.0 \text{ persons/veh}$ | $20.0\text{--}55.0$ | `[Assumption]` | Represents seated plus standing peak load on standard 40-seat institutional contract buses. |
| **`ASM_OCC_AUTO`**| **Baseline Auto-Rickshaw Occupancy ($O_{\text{auto}}$)** | $1.80 \text{ persons/veh}$ | $1.0\text{--}3.5$ | `[Survey-reported value]` | Reflects shared auto-rickshaw feeder usage between metro/bus stations and campus gates. |
| **`ASM_DETOUR`**  | **Carpooling Route Detour Penalty ($D_{\text{detour}}$)**| $1.10 \text{ (10% extra)}$ | $1.05\text{--}1.25$ | `[Assumption]` | Picking up passengers along a shared commute corridor requires residential deviations; modeled at a standard 10% route extension. |
| **`ASM_SHUTTLE_FC`**| **Campus Shuttle Fuel Economy** | $3.2 \text{ km/litre diesel}$ | $2.5\text{--}4.5$ | `[Source-derived value]` | Typical fuel efficiency of medium-to-heavy diesel institutional transit buses operating in Bengaluru urban traffic corridors. |
| **`ASM_SAMPLE_WARN`**| **Survey Sample Warning Threshold** | $n = 20$ | Fixed | `[Source-derived value]` | Statistical threshold below which small-sample variance invalidates naive campus-wide population extrapolation without explicit disclosures. |

---

## 4. Methodological Sensitivity Analysis

> The calculations below are illustrative sensitivity examples using unverified candidate values. They do not verify either factor or establish a production baseline.

To understand how variations in assumptions affect final carbon totals:

1. **Operating Days ($Y$):** A 10% change in academic operating days ($\pm 20$ days) produces an exact linear $\pm 10\%$ shift in total annual emissions.
2. **Carpool Detour Penalty ($D_{\text{detour}}$):** Increasing detour distance from 10% to 20% reduces net carpool carbon savings by approximately 12–15%, illustrating that poorly planned, meandering carpool routes diminish environmental benefits.
3. **Shuttle Breakeven Occupancy:** For an institutional diesel shuttle ($EF = 0.850 \text{ kg } CO_2/\text{km}$) running a 15 km route, replacing solo cars ($EF = 0.145 \text{ kg } CO_2/\text{km}$), the shuttle must displace at least:
   $$\frac{0.850}{0.145} \approx 5.86 \approx \mathbf{6 \text{ personal cars}}$$
   If a shuttle route diverts fewer than 6 cars (or fewer than ~7 solo car drivers), **the shuttle generates net positive carbon emissions**, polluting more than the private cars it replaces.

---

## 5. B3 Registry and Current Approval State

The server-controlled approved factor registry is implemented in `backend/factor_registry.py` and currently contains no approved records. A factor may enter that registry only after the project owner records an explicit approval decision and supporting review evidence. The application does not independently authenticate a cited publication.

The API's candidate path is separate from the approved registry. Candidate snapshots are marked unapproved and preserve the submitted value, version identifier, source description where available, and limitations. Caller-supplied provenance cannot grant approval. `0.145 kg CO2/veh-km` remains an unverified candidate. `0.150 kg CO2/veh-km` remains a test fixture only.

Factor metadata records category applicability and known fuel/powertrain applicability. The current activity request contains no fuel or powertrain field; consequently, the backend checks category but does not claim fuel/powertrain compatibility was checked. Fuel-specific candidates must not be interpreted as universal factors.
## Judges' Demo Factors and Assumptions

The demo endpoint requires four explicit caller-supplied motor-category factors and explicit activity/scenario assumptions. They are stored as demo request snapshots and labelled illustrative_unapproved by the backend. Caller text such as source descriptions is preserved as an explanation only; it is not checked for truth, source authenticity, publication quality, or owner approval. Demo factors cannot enter the approved registry through this endpoint. No factor value is supplied as a hidden default. Example values in BACKEND.md are request examples only, not recommended or scientifically validated factors.

Image counts are visible-object detections from one point in time. Applying an assumed number of commute cycles per detected vehicle is an additional user-provided modeling assumption, not a measurement made by YOLO. Scenario shares, shuttle service, and active-travel distance limits are explicit illustrative settings, not evidence of feasible policy uptake.
