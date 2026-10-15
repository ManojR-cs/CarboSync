# Architecture & Product Decision Register (ADR) — TraceTwin

**Document Type:** Formal Decision Records  
**Current Stage:** Requirements & Architecture Planning  
**Last Updated:** October 15, 2026  
**Auditor:** TraceTwin Architecture Review Board  

---

## Index of Architectural Decision Records

| ADR ID | Decision Topic | Status | Impact Area |
| :---: | :--- | :---: | :--- |
| **ADR-001** | Local Single-Laptop Deployment Architecture | `Confirmed` | Infrastructure & Deployment |
| **ADR-002** | Four Core Vehicle Categories & Baseline Exclusions | `Confirmed` | Domain Modeling & Methodology |
| **ADR-003** | Hybrid Data Collection & Strict Isolation of Evidence Streams | `Confirmed` | Data Architecture & Ingestion |
| **ADR-004** | Road-Route Commute Distance & Locality Minimization | `Confirmed` | GIS & Privacy Engineering |
| **ADR-005** | Fixed Emission Factors with Provenance Register | `Confirmed` | Carbon Accounting Engine |
| **ADR-006** | Sample-Based Baseline vs. Explicit Campus Projections | `Confirmed` | Statistics & UI Presentation |
| **ADR-007** | Three Core Digital Twin Scenarios with Added Emissions | `Confirmed` | Simulation Engine |
| **ADR-008** | Guarded Generative AI with Deterministic Fallback | `Confirmed` | AI Safety & Robustness |
| **ADR-009** | Pretrained Ultralytics YOLO11n with Human-in-the-Loop Review | `Confirmed` | Computer Vision Pipeline |
| **ADR-010** | Student Register Authorization Scope and Privacy Governance | `Needs verification` | Legal, Privacy & Compliance |
| **ADR-011** | Zero Pre-Built Code Hackathon Compliance Standard | `Confirmed` | Competition Regulatory Compliance |
| **ADR-012** | Proposed Technology Stack (FastAPI, SQLite, Vanilla JS) | `Proposed` | Implementation Engineering |
| **ADR-013** | Parallel Workstream Governance & Dedicated Integration Owner | `Confirmed` | Team Organization & Delivery |

---

## ADR-001: Local Single-Laptop Deployment Architecture

- **Decision ID:** `ADR-001`
- **Topic:** Target Deployment Environment and Infrastructure Scope.
- **Decision:** TraceTwin will be deployed and demonstrated exclusively on a single local laptop host running a local FastAPI server, an embedded SQLite database, and a local browser client. No public cloud hosting, Docker containers, or public domain DNS will be configured for the MVP.
- **Status:** `Confirmed`
- **Rationale:** 
  - Eliminates reliance on unstable hackathon venue Wi-Fi during the live judges' evaluation.
  - Removes cloud infrastructure provisioning costs, complex DevOps pipelines, and SSL configuration overhead.
  - Aligns with the beginner-friendly team profile, allowing all members to inspect and debug local runtime processes directly.
- **Consequences:**
  - The application cannot be simultaneously accessed by multiple remote evaluators over the internet without ad-hoc port forwarding (e.g., ngrok).
  - Production multi-tenant campus scalability is deferred to post-hackathon phases.
- **Open Concerns:** The host laptop must have sufficient CPU and RAM headroom to run FastAPI, browser rendering, and YOLO inference concurrently.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-002: Four Core Vehicle Categories & Baseline Exclusions

- **Decision ID:** `ADR-002`
- **Topic:** Vehicular Classification Boundaries and Exclusions.
- **Decision:** TraceTwin will recognize exactly four vehicle categories for emissions accounting:
  1. **Cars** (Internal combustion passenger automobiles)
  2. **Motorcycles and scooters** (Two-wheelers powered by petrol)
  3. **Buses and campus shuttles** (Contracted institutional coaches and public transit buses)
  4. **Other fuel-burning vehicles, including auto-rickshaws** (Three-wheelers, light delivery trucks, utility vans)  
  *Exclusions:* Electric Vehicles (EVs), walking, and cycling are explicitly excluded from the initial baseline calculation.
- **Status:** `Confirmed`
- **Rationale:**
  - Reflects the empirical composition of traffic observed at urban Indian university campuses.
  - Auto-rickshaws represent a significant campus feeder mode in Bengaluru but lack a distinct COCO class; grouping them under "Other fuel-burning vehicles" provides an honest, functional category.
  - Active transit (walking and cycling) produces zero tailpipe emissions and is excluded from vehicular emissions accounting.
  - Modeling EVs requires charging schedule logs, on-campus charger metering, and grid emission factors (e.g., CEA CO₂ baseline), which would overwhelm the 48-hour scope.
- **Consequences:**
  - The category "Other fuel-burning vehicles" aggregates disparate engine types (2-stroke/4-stroke auto-rickshaws and diesel light trucks), requiring a documented composite emission factor proxy.
  - Users with electric scooters or cars cannot log their trips in the baseline audit.
- **Open Concerns:** Ensuring the UI clearly explains why EVs are excluded so evaluators do not perceive it as an oversight.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-003: Hybrid Data Collection & Strict Isolation of Evidence Streams

- **Decision ID:** `ADR-003`
- **Topic:** Integration and Separation of Disparate Data Streams.
- **Decision:** The platform will ingest data from multiple sources (parking snapshots, attendance registers, commuter surveys) but enforces strict computational isolation between them:
  - Parking photographs provide point-in-time occupancy validation and CV demonstration, but **will not** be treated as total daily unique commuters.
  - Attendance registers validate physical campus activity days, but **will not** be used to infer transportation mode.
  - Commuter surveys provide mode share and average trip distances, but **will not** be silently summed with physical parking counts.
- **Status:** `Confirmed`
- **Rationale:**
  - Prevents severe double-counting (e.g., adding 100 cars in a photo to 80 cars reported in a survey).
  - A single parking snapshot represents a static slice of time; treating it as daily traffic ignores turn-over, carpooling, off-campus parking, and drop-offs.
- **Consequences:**
  - The system must feature separate UI workflows for parking image audits versus commute activity entry.
  - Requires clear explanatory copy on the dashboard to educate users on the distinction.
- **Open Concerns:** Users may expect an automated pipeline that turns a parking photo directly into an annual carbon total. The documentation and UI must explicitly push back on this flawed assumption.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-004: Road-Route Commute Distance & Locality Minimization

- **Decision ID:** `ADR-004`
- **Topic:** Commute Distance Estimation and Privacy Preservation.
- **Decision:** Commute distances will be estimated using road-route distances from origin localities to the campus destination via a mapping service or lookup table. Origins will be captured strictly at the generalized neighborhood, ward, or postal code level (e.g., "Koramangala 5th Block", "Yelahanka"). Exact street addresses and house numbers are strictly prohibited.
- **Status:** `Confirmed`
- **Rationale:**
  - Road-route distance reflects real-world driving detours, traffic corridors, and physical road geography far better than straight-line Euclidean distance.
  - Capturing exact home addresses creates significant privacy vulnerabilities, violates data minimization principles, and introduces legal liability.
  - Locality-level centroids introduce negligible error (<5%) over a typical 10–25 km urban university commute while fully preserving student anonymity.
- **Consequences:**
  - The platform must maintain or query a locality-to-campus distance lookup matrix.
  - If third-party mapping API access fails or is restricted, manual distance entry must serve as an immediate fallback.
- **Open Concerns:** Verification of whether transmitting locality names to external mapping APIs requires institutional data governance clearance.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-005: Fixed Emission Factors with Provenance Register

- **Decision ID:** `ADR-005`
- **Topic:** Selection, Unit Standardization, and Provenance of Carbon Factors.
- **Decision:** The calculation engine will apply fixed, category-specific tailpipe emission factors expressed in $\text{kg } CO_2/\text{veh-km}$. Every factor will be documented in a transparent factor register with its publication source, geographic context, and approximation notes. Users will have the ability to inspect and override these factors via an audit drawer.
- **Status:** `Confirmed`
- **Rationale:**
  - Eliminates ambiguity and ensures deterministic, reproducible mathematical outcomes.
  - Distinguishes tailpipe $CO_2$ from full lifecycle $CO_2e$, preventing misleading claims.
  - Prevents fatal unit mismatch errors (such as multiplying vehicle distances by passenger-km factors).
- **Consequences:**
  - Fixed factors cannot dynamically account for vehicle age, fuel quality (e.g., BS-IV vs. BS-VI), or driving cycle variations (stop-and-go Bengaluru traffic). This limitation must be explicitly disclosed in the methodology panel.
- **Open Concerns:** Literature sources for Indian road transport emission factors (e.g., India GHG Program, ARAI) exhibit slight variations; the team must freeze a single defensible citation set during kickoff.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-006: Sample-Based Baseline vs. Explicit Campus Projections

- **Decision ID:** `ADR-006`
- **Topic:** Statistical Representation of Small Survey Samples ($n < 20$).
- **Decision:** The primary headline metric on the dashboard will represent a **Sample-Based Baseline** reflecting the surveyed cohort. A campus-wide projected total will only be displayed if the user explicitly activates an "Extrapolate to Campus" toggle, which requires inputting the total campus population and explicitly accepts documented mode-share assumptions.
- **Status:** `Confirmed`
- **Rationale:**
  - Given an expected survey sample under 20 responses, automatic campus-wide extrapolation is statistically indefensible and academically dishonest.
  - Guardrails prevent evaluators from dismissing TraceTwin as a "hallucinatory" or scientifically flawed tool.
- **Consequences:**
  - The UI must render dual baseline modes: `Sample-Based Emissions` (empirical audit) and `Campus Projected Emissions` (scenario extrapolation with warning banners).
- **Open Concerns:** Ensuring judges understand that presenting the sample-based total as default is a strength of scientific integrity rather than a missing feature.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-007: Three Core Digital Twin Scenarios with Added Emissions

- **Decision ID:** `ADR-007`
- **Topic:** Scenario Selection and Counterfactual Accounting.
- **Decision:** The Digital Twin engine will support exactly three counterfactual scenarios:
  1. **Fewer Commute Days:** Remote learning / work days reducing operating schedule ($Y$).
  2. **Carpooling Incentive:** Increased vehicle occupancy reducing car trips, penalized by a 10% average pickup detour distance.
  3. **Institutional Bus / Campus Shuttle:** Shifting private commuters into institutional transit, **with mandatory calculation of the added fuel emissions generated by the operating shuttles**.  
  *Exclusion:* Electric vehicle replacement scenarios are excluded from the MVP.
- **Status:** `Confirmed`
- **Rationale:**
  - Covers the three most actionable, non-capital-intensive mobility policies available to a university.
  - Mandating added shuttle emissions prevents "free transit" fallacies where adding a bus magically erases emissions without accounting for its diesel burn.
  - Limiting scope to three scenarios guarantees complete, robust implementation within 48 hours.
- **Consequences:**
  - The shuttle calculation formula must handle edge cases where low passenger uptake results in negative net savings (net increase in campus emissions).
- **Open Concerns:** Establishing a defensible default fuel consumption factor for institutional diesel buses in urban traffic.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-008: Guarded Generative AI with Deterministic Fallback

- **Decision ID:** `ADR-008`
- **Topic:** Integration Guardrails for Large Language Models.
- **Decision:** Generative AI will be employed strictly as a qualitative narrative explainer and policy ranker. The LLM will receive zero numerical calculation responsibility and zero personal data. LLM responses will be intercepted by a strict schema validator. If the API times out (>4000ms), fails, or outputs invalid JSON, the system will immediately render a deterministic, rule-based recommendation plan labeled `"Rule-based plan (AI unavailable)"`.
- **Status:** `Confirmed`
- **Rationale:**
  - Completely eliminates the risk of AI hallucinating numerical carbon savings during a live hackathon presentation.
  - Ensures the application remains 100% functional even if the venue loses internet access or the LLM API quota is exhausted.
- **Consequences:**
  - Requires maintaining a pre-authored deterministic catalog of rule-based policy recommendations mapped to quantitative triggers.
  - Developers must author strict Pydantic JSON validation schemas in FastAPI.
- **Open Concerns:** Selecting the fastest, most cost-effective LLM provider (e.g., GPT-4o-mini or Gemini 1.5 Flash) to minimize latency during live demonstrations.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-009: Pretrained Ultralytics YOLO11n with Human-in-the-Loop Review

- **Decision ID:** `ADR-009`
- **Topic:** Computer Vision Model Selection and Detection Workflow.
- **Decision:** TraceTwin will use the pretrained Ultralytics `yolo11n.pt` model executing locally on the host CPU. Detections will be processed via OpenCV and rendered on an interactive frontend canvas where a human reviewer must inspect, delete false positives, reclassify ambiguous vehicles, and manually add missed vehicles before counts are permanently saved as `[Human-confirmed observation]`.
- **Status:** `Confirmed`
- **Rationale:**
  - The YOLO11 nano model (~5.4 MB) downloads automatically on first run, fits in lightweight memory, and executes inference in <3 seconds on standard laptop CPUs without CUDA/GPU dependencies.
  - Pretrained models struggle with dense Indian parking lots, occlusion, and three-wheelers; embedding a human verification loop transforms an imperfect ML model into a reliable enterprise auditing workflow.
- **Consequences:**
  - Frontend must implement interactive mouse controls for bounding box editing on an HTML5 Canvas or SVG overlay.
- **Open Concerns:** Testing whether `yolo11n.pt` frequently misses motorcycles parked in tight rows or requires manual reclassification for auto-rickshaws.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-010: Student Register Authorization Scope and Privacy Governance

- **Decision ID:** `ADR-010`
- **Topic:** Privacy Scope and Compliance for Student Register Access.
- **Decision:** While specific administrative authorization to access student register information is reported by the team, the platform enforces strict data minimization: no raw register tables, names, or IDs will be uploaded to the database. Only aggregated attendance-day distributions and postal-code distance groupings will be ingested. Downstream transmission of individual records to external third parties (mapping or AI) is strictly barred.
- **Status:** `Needs verification`
- **Rationale:**
  - Upholds Indian Digital Personal Data Protection (DPDP) Act compliance and basic institutional ethics.
  - Protects the team and university from potential data privacy violations.
- **Consequences:**
  - Requires writing preprocessing scripts or manual aggregation forms to convert raw registers into anonymized summary inputs prior to database ingestion.
- **Open Concerns:** The exact institutional permissions regarding student address processing must be formally verified with campus advisors during the kickoff phase.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-011: Zero Pre-Built Code Hackathon Compliance Standard

- **Decision ID:** `ADR-011`
- **Topic:** Adherence to Code Clash 2.0 Hackathon Competition Rules.
- **Decision:** The project repository prior to kickoff will contain exclusively documentation, architectural designs, data dictionaries, mathematical specifications, test protocols, and execution roadmaps. Zero application source code (Python, JS, HTML, CSS, SQL, shell scripts) or starter templates will be generated or committed before the official competition start time.
- **Status:** `Confirmed`
- **Rationale:**
  - Preserves complete integrity and avoids disqualification under the event rule: *"All code must be written during the event and pre-built projects/templates are prohibited."*
  - Clear documentation enables the team to write clean, purposeful code rapidly during the event with the assistance of interactive AI tools.
- **Consequences:**
  - All software development must take place within the 48-hour live competition window.
- **Open Concerns:** Ensuring all team members understand that pre-writing code secretly creates disqualification risk.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-012: Proposed Technology Stack (FastAPI, SQLite, Vanilla JS)

- **Decision ID:** `ADR-012`
- **Topic:** Selection of Implementation Technologies.
- **Decision:** The proposed stack consists of:
  - Backend: Python 3.11 with FastAPI and Uvicorn.
  - Computer Vision: Ultralytics YOLO11n running on local CPU with OpenCV (`cv2`).
  - Database: SQLite3 via standard Python libraries.
  - Frontend: Native Vanilla HTML5, modern CSS3, and ES6+ JavaScript.
  - Charting: Chart.js via local static script.
  - Guarded AI: Python `urllib` / `httpx` client communicating with an external LLM API.
- **Status:** `Proposed` (Subject to live environment verification at kickoff).
- **Rationale:**
  - Zero build step on the frontend; changes reload instantly in the browser.
  - Python backend provides native compatibility with PyTorch, YOLO, and mathematical calculations.
  - SQLite requires zero configuration, zero daemon management, and zero credential setup.
- **Consequences:**
  - Frontend components must be organized cleanly in modular JS files to avoid spaghetti code.
- **Open Concerns:** Ensuring Python 3.11 and PyTorch install smoothly on the primary laptop during kickoff setup.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).

---

## ADR-013: Parallel Workstream Governance & Dedicated Integration Owner

- **Decision ID:** `ADR-013`
- **Topic:** Team Execution Model and Integration Leadership.
- **Decision:** Work will be divided into four parallel workstreams (A: Computer Vision, B: Carbon Engine & Methodology, C: Frontend & Canvas UI, D: Backend, Storage & AI Guard). Workstream D will also serve as the dedicated **Integration Owner**, responsible for maintaining the shared API contract, validating schema compatibility, and driving integration checkpoints at Hours 14, 28, and 36.
- **Status:** `Confirmed`
- **Rationale:**
  - Beginner teams frequently fail at integration because parallel workstreams drift apart without a unifying contract or dedicated owner.
  - The shared API contract acts as a binding specification, allowing frontend and backend to develop in parallel using mock data.
- **Consequences:**
  - Team members must not alter endpoint paths, request keys, or response payloads without explicit agreement from the Integration Owner.
- **Open Concerns:** Maintaining discipline so team members don't bypass the API contract when under time pressure.
- **Date / Stage:** Pre-Hackathon Planning (October 15, 2026).
