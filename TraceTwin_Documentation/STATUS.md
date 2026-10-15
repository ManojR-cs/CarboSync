# Living Project Status Register — TraceTwin

**Document Type:** Living Status & Audit Register  
**Current Stage:** `Requirements & Architecture Planning` (Pre-Hackathon Preparation)  
**Last Updated:** October 15, 2026  
**Auditor / Maintainer:** TraceTwin Integration Owner  

---

## 1. Current Project Stage Summary

TraceTwin is currently in the **Pre-Hackathon Requirements & Architecture Phase**. 

In strict compliance with the Dayananda Sagar University Code Clash 2.0 hackathon rules prohibiting pre-built software or templates:
- **Application Code Status:** 0 lines of executable source code written.
- **Database Status:** 0 database tables instantiated.
- **Test Status:** 0 test cases executed.
- **Artifact Status:** Architecture, product requirements, data dictionary, mathematical methodologies, test protocols, and execution roadmaps are fully drafted and cross-validated.

---

## 2. Confirmed Decisions Register

The following product and architectural decisions have been explicitly approved by the team:

| Decision ID | Item | Status | Approved Detail |
| :---: | :--- | :---: | :--- |
| **CD-01** | **Target Deployment** | `Confirmed` | Single-laptop local execution (FastAPI backend, SQLite, Vanilla HTML/CSS/JS frontend). No public URL required. |
| **CD-02** | **Vehicle Categories** | `Confirmed` | Exactly four categories: (1) Cars, (2) Motorcycles and scooters, (3) Buses and campus shuttles, (4) Other fuel-burning vehicles, including auto-rickshaws. |
| **CD-03** | **Baseline Exclusions** | `Confirmed` | Electric vehicles (EVs), walking, and cycling are excluded from the initial baseline calculation. |
| **CD-04** | **Numerical Calculation Authority** | `Confirmed` | All numerical emissions and scenario savings are computed exclusively by a deterministic Python calculation engine. |
| **CD-05** | **Guarded AI Role** | `Confirmed` | Generative AI is restricted to qualitative policy explanations and ranking. Strictly isolated from numerical claims; deterministic rule-based fallback mandatory. |
| **CD-06** | **Evidence Stream Isolation** | `Confirmed` | Parking photographs are point-in-time snapshot observations and must never be summed with survey-derived daily commuter counts. |
| **CD-07** | **Digital Twin Scenarios** | `Confirmed` | Exactly three scenarios: (1) Fewer commute days, (2) Carpooling, (3) Bus/shuttle intervention (with added diesel emissions calculated). |
| **CD-08** | **Student Privacy Standard** | `Confirmed` | Zero student names, registration IDs, or exact street addresses stored in database or transmitted to cloud services. Locality-level aggregation only. |

---

## 3. Proposed but Unimplemented Features

The following technical components are specified in [SPECIFICATIONS.md](file:///c:/Users/yasha/OneDrive/Documents/Trace_Twin/TraceTwin_Documentation/SPECIFICATIONS.md) and scheduled for live authoring during the 48-hour hackathon:

| Feature Specification | Category | Status | Target Workstream |
| :--- | :---: | :---: | :---: |
| Local FastAPI server skeleton with CORS & static file mounts | Backend | `Proposed` | Workstream D |
| Ultralytics YOLOv8n CPU pipeline with bounding-box serialization | CV | `Proposed` | Workstream A |
| HTML5 Canvas overlay for interactive box editing and reclassification | Frontend | `Proposed` | Workstream C |
| Pure-Python deterministic baseline emissions engine ($\text{VKT} \times EF$) | Carbon Engine | `Proposed` | Workstream B |
| Digital Twin scenario engine with carpool detours and added shuttle fuel | Carbon Engine | `Proposed` | Workstream B |
| SQLite database schema and persistence layer | Backend | `Proposed` | Workstream D |
| Guarded LLM proxy with JSON schema interceptor and 4-second timeout | AI Guard | `Proposed` | Workstream D |
| Deterministic rule-based fallback recommendation catalog | AI Guard | `Proposed` | Workstream D |
| Interactive Chart.js mode-share breakdowns and scenario comparisons | Frontend | `Proposed` | Workstream C |
| Printable HTML/PDF methodology audit and transparency report | Reporting | `Proposed` | Workstream C |

---

## 4. Verified Implementation & Execution Evidence

> [!NOTE]
> **Implementation Audit:** In compliance with the Code Clash 2.0 hackathon code-writing constraints, **no functional implementation code has been authored prior to the event**.
>
> All rows in this register remain pending until verified during live competition hours:

| Component | Code Files Exist? | Execution Verified? | Current State |
| :--- | :---: | :---: | :--- |
| **Backend API Server** | No | No | `Unimplemented` |
| **CV Inference Pipeline** | No | No | `Unimplemented` |
| **Canvas Review Interface** | No | No | `Unimplemented` |
| **Carbon Calculation Engine** | No | No | `Unimplemented` |
| **Digital Twin Simulator** | No | No | `Unimplemented` |
| **Guarded AI Proxy** | No | No | `Unimplemented` |
| **SQLite Persistence** | No | No | `Unimplemented` |

---

## 5. Tests Actually Run

> [!NOTE]
> **Test Audit:** No live unit tests, API tests, or CV validation runs have been executed. Test definitions are documented in [TEST_PLAN.md](file:///c:/Users/yasha/OneDrive/Documents/Trace_Twin/TraceTwin_Documentation/TEST_PLAN.md) awaiting live execution.

| Test ID | Category | Target Suite | Status | Execution Evidence |
| :--- | :--- | :--- | :---: | :--- |
| `T-IMG-01` | Image Upload Bounds | Upload Validation | `Planned` | Awaiting live code execution |
| `T-DET-01` | YOLO Class Mapping | CV Inference | `Planned` | Awaiting live code execution |
| `T-HUM-01` | Canvas Box Deletion | Human Verification | `Planned` | Awaiting live code execution |
| `T-CALC-01` | Baseline VKT × EF | Carbon Engine | `Planned` | Awaiting live code execution |
| `T-SCEN-03` | Shuttle Added Emissions | Digital Twin | `Planned` | Awaiting live code execution |
| `T-GUARD-01`| AI Hallucination Guard | Guarded AI | `Planned` | Awaiting live code execution |
| `T-FAIL-01` | AI Fallback Activation | Guarded AI | `Planned` | Awaiting live code execution |
| `T-E2E-01` | Full User Journey | Integration | `Planned` | Awaiting live code execution |

---

## 6. Active Blockers & Critical Risks

| Blocker / Risk ID | Description | Severity | Status | Mitigation Action |
| :---: | :--- | :---: | :---: | :--- |
| **BLK-01** | **Target Laptop Dependency Verification:** PyTorch CPU and Ultralytics must be validated on the physical competition laptop during Hour 0. | High | `Open` | Perform dry-run package installation immediately upon hackathon room entry. |
| **BLK-02** | **Mapping API Privacy & Quota Clearance:** Determining whether Google Maps / OSRM API can be used without leaking student coordinates or hitting rate limits. | Medium | `Needs verification` | Build manual distance entry UI as primary path; treat live mapping as optional progressive enhancement. |
| **RSK-01** | **Sample Size Bias ($n < 20$):** Unrepresentative student survey sample could lead to deceptive campus-wide claims. | High | `Mitigated in Design` | Design restricts headline display to sample-based totals; campus projection requires manual toggle with explicit assumptions. |
| **RSK-02** | **Guarded AI Hallucination:** LLM generating fake emissions numbers on demo stage. | Critical | `Mitigated in Design` | Architectural boundary prevents LLM from generating numbers; deterministic engine injects values; fallback catalog ready. |

---

## 7. Open Questions Requiring Team Decision at Kickoff

1. **Auto-rickshaw CV Detection Fidelity:** Will `yolov8n.pt` classify auto-rickshaws as `truck`, `car`, or miss them completely?  
   *Action:* Test 3 sample campus gate photos during Hour 1.
2. **Student Register Authorization Scope:** While access is confirmed in principle, does authorization permit third-party API transmission of postal codes?  
   *Action:* Privacy Reviewer to enforce strictly local in-memory processing.
3. **Primary Emission Factor Set:** Should the baseline use India GHG Program factors, ARAI figures, or DEFRA values adjusted for India?  
   *Action:* Review [SOURCES_AND_ASSUMPTIONS.md](file:///c:/Users/yasha/OneDrive/Documents/Trace_Twin/TraceTwin_Documentation/SOURCES_AND_ASSUMPTIONS.md) and freeze factor constants in Hour 2.

---

## 8. Immediate Next Actions (Kickoff Phase)

- [ ] Complete cross-validation review of all 11 documentation artifacts.
- [ ] Confirm team workstream assignments (Specialists A, B, C, D) as defined in [EXECUTION_PLAN.md](file:///c:/Users/yasha/OneDrive/Documents/Trace_Twin/TraceTwin_Documentation/EXECUTION_PLAN.md).
- [ ] Prepare clean Python 3.11 virtual environment on the evaluation laptop at official event kickoff.
- [ ] Implement Vertical Slice 1 (Walking Skeleton) within first 14 hours.

---

## 9. Change History & Audit Log

| Date / Timestamp | Version | Author / Role | Changes Logged |
| :--- | :---: | :--- | :--- |
| **2026-10-15 13:00** | `0.1.0` | Integration Owner | Initialized Status Register; documented baseline pre-hackathon status; certified 0 pre-built lines of code. |
