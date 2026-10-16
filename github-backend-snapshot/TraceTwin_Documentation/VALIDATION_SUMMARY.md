# Cross-Document Consistency & Quality Validation Summary — TraceTwin

**Document Type:** Formal Quality Assurance & Consistency Audit  
**Current Stage:** Pre-Hackathon Quality Gate  
**Audit Date:** October 15, 2026  
**Auditor:** TraceTwin Cross-Functional Quality Review Board  

---

## 1. Executive Validation Verdict

> **Validation Status:** `PASSED WITH NOTED UNRESOLVED DECISIONS`  
> The 11 core documentation files in the `TraceTwin_Documentation` suite have been comprehensively reviewed and cross-checked. No internal contradictions, illegal code artifacts, or unsupported status claims were identified.

---

## 2. Comprehensive Consistency Verification Matrix

| Quality Control Check | Required Invariant | Audit Findings Across Documentation Suite | Audit Status |
| :--- | :--- | :--- | :---: |
| **1. Vehicle Categories** | Exactly 4 categories: (1) Cars, (2) Motorcycles and scooters, (3) Buses and campus shuttles, (4) Other fuel-burning vehicles, including auto-rickshaws. | Verified identical across `README.md`, `PRD.md`, `SPECIFICATIONS.md`, `CONTEXT.md`, `STATUS.md`, `DECISIONS.md`, `DATA_DICTIONARY.md`, `METHODOLOGY.md`, `TEST_PLAN.md`, `EXECUTION_PLAN.md`, and `SOURCES_AND_ASSUMPTIONS.md`. | **Compliant** |
| **2. Baseline Exclusions** | Electric Vehicles (EVs), walking, and cycling strictly excluded from initial baseline. | Verified explicitly stated in all documents. EV modeling documented as post-hackathon Phase 2. Active transit excluded from tailpipe accounting. | **Compliant** |
| **3. Digital Twin Scenarios** | Exactly 3 scenarios: (1) Fewer commute days, (2) Carpooling, (3) Bus/shuttle intervention (with mandatory added diesel fuel accounting). | Verified identical across all 11 files. Added shuttle emissions formula ($VKT \times EF_{\text{shuttle}}$) and negative net savings handling explicitly documented. | **Compliant** |
| **4. Student Data Privacy** | No individual addresses, names, student IDs, or raw attendance logs required or stored in database. | Confirmed: `DATA_DICTIONARY.md`, `SPECIFICATIONS.md`, `PRD.md`, and `CONTEXT.md` prohibit PII columns. Geographic data minimized to coarse localities. | **Compliant** |
| **5. Authorization Governance** | Student register authorization noted as reported by team, but downstream scope and third-party transmission flagged for verification. | Confirmed: Recorded as `Needs verification` in `DECISIONS.md` (ADR-010) and `STATUS.md`. Third-party mapping transmission isolated. | **Compliant** |
| **6. Survey Representation** | Sample under 20 ($n < 20$) must NOT be claimed as statistically representative by default. | Confirmed: Default headline metric is "Sample-Based Baseline". Campus-wide projection locked behind manual toggle with explicit assumption disclosures. | **Compliant** |
| **7. Parking Count Separation** | Parking snapshot photo counts must NOT be treated as daily unique commuters or added to survey counts. | Confirmed: Documented as non-negotiable Invariant 1 in `CONTEXT.md`, `METHODOLOGY.md` Section 5, `PRD.md` Section 5.1, and `TEST_PLAN.md` (T-DUP-02). | **Compliant** |
| **8. Emission Factor Provenance** | No unsupported factor values; all factors carry units, source, geography, and approximation disclosures. | Confirmed: `SOURCES_AND_ASSUMPTIONS.md` contains structured register with India GHG Program / ARAI citations. Fixed approximation limits disclosed. | **Compliant** |
| **9. Unit Invariants (VKT vs PKT)** | Clear separation between $\text{kg } CO_2/\text{veh-km}$ and $\text{kg } CO_2/\text{pass-km}$. No mixing of units. | Confirmed: Invariant 2 in `CONTEXT.md` and Section 2 of `METHODOLOGY.md`. Test suite `TS-UNIT` explicitly traps unit violations. | **Compliant** |
| **10. Metric Scope (CO₂ vs CO₂e)** | Strict tailpipe $CO_2$ scope. CEA grid factor explicitly excluded from road tailpipe emissions. | Confirmed: Disclosed in `METHODOLOGY.md` Section 1 and `SOURCES_AND_ASSUMPTIONS.md` Section 2.1. CEA grid factor explained as electricity-only. | **Compliant** |
| **11. Guarded AI Numerical Isolation**| Generative AI strictly forbidden from calculating or inventing numerical emissions claims. | Confirmed: Guarded AI proxy intercepts JSON; deterministic engine attaches numbers; prompt contains zero calculation duty. | **Compliant** |
| **12. Deterministic AI Fallback** | Fallback to rule-based recommendations labeled `"Rule-based plan (AI unavailable)"`. | Confirmed: Identical fallback label and catalog documented across `PRD.md`, `SPECIFICATIONS.md`, `CONTEXT.md`, `TEST_PLAN.md`, and `DECISIONS.md`. | **Compliant** |
| **13. Target Deployment** | Local single-laptop deployment (FastAPI + SQLite + Vanilla JS). Zero cloud requirement. | Confirmed: Stated consistently in `README.md`, `PRD.md`, `SPECIFICATIONS.md`, `DECISIONS.md`, and `EXECUTION_PLAN.md`. | **Compliant** |
| **14. Team Roles & Capabilities** | Beginner-friendly team with 4 members. Roles assigned as functional profiles, not invented names. | Confirmed: Workstreams A, B, C, D allocated by role profile (CV Specialist, Engine Specialist, UI Specialist, Backend/Integration Owner). | **Compliant** |
| **15. Pre-Built Code Prohibition** | Zero pre-built code, templates, starter projects, or executable files committed prior to kickoff. | Confirmed: All schemas and endpoints marked `Proposed`; implementation status confirmed as 0 lines of code in `STATUS.md`. | **Compliant** |
| **16. Execution & Test Honesty** | Zero features claimed as implemented or tested without physical execution evidence. | Confirmed: All 18 test cases in `TEST_PLAN.md` marked `Planned` / `Untested`; `STATUS.md` certifies 0 executed tests. | **Compliant** |

---

## 3. Register of Unresolved Decisions & Open Technical Questions

The following decisions and technical questions remain open and must be formally resolved during **Hour 0 – Hour 2 of the hackathon kickoff**:

### Unresolved Decision 1: Primary Emission Factor Freeze
- **Description:** Whether to standardize on India GHG Program (2015) factors or more recent ARAI/CPCB factors for the baseline engine constants.
- **Current Status:** `Needs verification` (Cataloged in `SOURCES_AND_ASSUMPTIONS.md`).
- **Required Action at Kickoff:** Environmental Engine Specialist (Workstream B) must review the candidate table and freeze fixed values for `EF_CAR`, `EF_MOTO`, `EF_BUS`, and `EF_AUTO` by Hour 2.

### Unresolved Decision 2: Student Register Authorization Scope
- **Description:** The team reported authorization to use student register data. However, does this permit transmitting postal codes or locality names to an external third-party geocoding/routing API (e.g., Google Maps)?
- **Current Status:** `Needs verification` (Cataloged in `DECISIONS.md` ADR-010).
- **Required Action at Kickoff:** Privacy Reviewer / Backend Lead must confirm whether to enable live external mapping queries or rely on a static, local Bangalore locality lookup table.

### Unresolved Decision 3: YOLOv8n Auto-Rickshaw Detection Accuracy
- **Description:** The standard COCO dataset does not have an "auto-rickshaw" class. YOLOv8n typically tags them as `truck`, `car`, or fails to detect them in dense parking.
- **Current Status:** `Needs verification` (Cataloged in `SPECIFICATIONS.md` Section 3.2).
- **Required Action at Kickoff:** CV Specialist (Workstream A) must test 3 campus gate photographs during Hour 1 to determine whether the manual reclassification canvas tool is sufficient or if custom heuristic bounding-box thresholds are required.

### Unresolved Decision 4: Target Laptop CPU Inference Latency
- **Description:** Confirming that `yolov8n.pt` executes within the 3.5-second performance threshold on the specific hardware provided by the team.
- **Current Status:** `Needs verification` (Cataloged in `STATUS.md` BLK-01).
- **Required Action at Kickoff:** Run a dry-run inference test script on a sample $1920 \times 1080$ image immediately after Python environment setup in Hour 0.

---

## 4. Final Sign-Off Checklist for Hackathon Kickoff

- [x] All 11 markdown documentation files created in `TraceTwin_Documentation/`.
- [x] Cross-file consistency verified for vehicle categories, scenarios, units, and privacy rules.
- [x] Zero pre-built executable source code or starter templates created.
- [x] All APIs, schemas, and database designs marked as `Proposed`.
- [x] All tests marked as `Planned` / `Untested`.
- [x] Unresolved technical and governance decisions clearly identified for kickoff resolution.
