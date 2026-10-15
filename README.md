# CarboSync / TraceTwin: Campus Commute Emissions Intelligence Platform

> **Tagline:** See the traffic. Trace the carbon. Test the fix.

[![Event](https://img.shields.io/badge/Event-DSU%20Code%20Clash%202.0-blue.svg)](https://github.com/ManojR-cs/CarboSync)
[![Track](https://img.shields.io/badge/Track-Carbon%20Footprint%20Intelligence-green.svg)](https://github.com/ManojR-cs/CarboSync)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Planning%20%26%20Architecture-orange.svg)](TraceTwin_Documentation/STATUS.md)

---

## 1. Executive Summary

**TraceTwin** (project repository **CarboSync**) is a campus commute-emissions estimation and simulation platform developed for the **Dayananda Sagar University Code Clash 2.0 Hackathon (October 15–16, 2026)**.

The platform provides a transparent, defensible, and reproducible pipeline to answer three core questions for university decision-makers:
1. **What commute emissions can we estimate from the empirical evidence available to a campus?**
2. **Which interventions (hybrid schedules, carpool lanes, transit shuttles) will verifiably reduce those emissions?**
3. **How can the system explain calculations and data limitations transparently without greenwashing or speculation?**

$$\text{Campus Parking Photos} \longrightarrow \text{Pretrained CV Detector} \longrightarrow \text{Human Verification} \longrightarrow \text{Deterministic Carbon Engine} \longrightarrow \text{Digital Twin Scenarios} \longrightarrow \text{Guarded AI Explanations}$$

### The Core Architectural Principle
> **AI may detect objects and explain results, but deterministic calculations and documented emission factors must control all numerical emissions claims.**

---

## 2. Critical Hackathon Compliance Statement

The official Code Clash 2.0 hackathon website stipulates that:
- **All code must be written during the event.**
- **Pre-built projects, starter templates, and pre-written code repositories are strictly prohibited.**

In full adherence to these regulations:
- This repository prior to competition kickoff contains **exclusively planning, architecture specifications, mathematical methodologies, data contracts, and verification plans**.
- **Zero executable application code, pre-built templates, or hidden scripts exist.**
- 100% of functional application code (FastAPI backend, YOLO inference pipeline, interactive Canvas review interface, SQLite database, and Chart.js dashboards) will be authored live during the official 48-hour hackathon window.

---

## 3. Complete Documentation Suite

All planning and engineering specifications are housed in [`TraceTwin_Documentation/`](TraceTwin_Documentation/):

| Document | Description |
| :--- | :--- |
| 📖 [README.md](TraceTwin_Documentation/README.md) | Documentation suite orientation, technology stack, and scope boundaries. |
| 📋 [PRD.md](TraceTwin_Documentation/PRD.md) | Product Requirements Document: problem statement, personas, functional requirements (FR-1 to FR-8), NFRs, MoSCoW priorities, and all 14 critical project risks. |
| 🏗️ [SPECIFICATIONS.md](TraceTwin_Documentation/SPECIFICATIONS.md) | Technical architecture, YOLOv8n CPU pipeline, Canvas human-in-the-loop review, pure-Python deterministic engine, REST API contracts, and SQLite schema. |
| 🧠 [CONTEXT.md](TraceTwin_Documentation/CONTEXT.md) | Developer context, invariant mathematical rules, privacy boundaries, 6 evidence labels, and AI assistant behavior guidelines. |
| 📊 [STATUS.md](TraceTwin_Documentation/STATUS.md) | Living project status register: stage certification (0 lines of code, 0 tests run), confirmed decisions, proposed features, and audit trail. |
| 🏛️ [DECISIONS.md](TraceTwin_Documentation/DECISIONS.md) | 13 formal Architectural Decision Records (ADRs) covering single-laptop hosting, vehicle classes, factor provenance, and guarded AI fallback. |
| 📚 [DATA_DICTIONARY.md](TraceTwin_Documentation/DATA_DICTIONARY.md) | Conceptual entity definitions (Assessment, ParkingObservation, DetectionAndCorrection, CommuteInput, EmissionFactor, Scenario, AIRecommendation) with zero student PII. |
| 🔬 [METHODOLOGY.md](TraceTwin_Documentation/METHODOLOGY.md) | Carbon accounting methodology: tailpipe $\text{kg } CO_2$ boundary, VKT vs. PKT rules, carpool detours ($D_{\text{detour}} = 1.10$), shuttle added fuel emissions, and anti-double-counting. |
| 🧪 [TEST_PLAN.md](TraceTwin_Documentation/TEST_PLAN.md) | 18 test cases across 11 test suites (CV bounds, hand-calculated benchmarks, unit isolation, AI number stripping, fallback activation, and live E2E demo script). |
| ⏱️ [EXECUTION_PLAN.md](TraceTwin_Documentation/EXECUTION_PLAN.md) | 48-hour roadmap across 4 parallel workstreams (A: CV, B: Engine, C: Frontend, D: Backend/Integration Owner), vertical slice 1, integration checkpoints, and cut lines. |
| 📑 [SOURCES_AND_ASSUMPTIONS.md](TraceTwin_Documentation/SOURCES_AND_ASSUMPTIONS.md) | Emission factor register (India GHG Program, ARAI, CPCB), critical analysis of the CEA grid-factor fallacy, and register of baseline operational assumptions. |
| ✅ [VALIDATION_SUMMARY.md](TraceTwin_Documentation/VALIDATION_SUMMARY.md) | Cross-document consistency verification matrix across all 16 prompt invariants, unresolved technical questions, and kickoff sign-off checklist. |

---

## 4. Proposed Architecture & Technology Stack

- **Frontend:** Vanilla HTML5, modern CSS3 (custom glassmorphism dark theme), native ES6+ JavaScript.
- **Visualizations:** HTML5 Canvas (interactive bounding box review) & Chart.js (emissions breakdowns).
- **Backend Application Server:** Python 3.11 with FastAPI and Uvicorn.
- **Computer Vision:** Ultralytics YOLOv8 Nano (`yolov8n.pt`) running on local CPU.
- **Storage Tier:** Embedded SQLite3.
- **Guarded Generative AI:** Strict JSON schema validator with deterministic rule-based fallback labeled `"Rule-based plan (AI unavailable)"`.
- **Target Deployment:** Local single-laptop execution.

---

## 5. Vehicle Scope & Core Scenarios

### Supported Vehicle Categories
1. **Cars** (Personal passenger automobiles)
2. **Motorcycles and scooters** (Two-wheelers)
3. **Buses and campus shuttles** (Institutional coaches)
4. **Other fuel-burning vehicles, including auto-rickshaws** (Three-wheelers & utility vehicles)

*Walking, cycling, and electric vehicles (EVs) are explicitly excluded from the initial baseline.*

### Three Digital Twin Scenarios
1. **Fewer Commute Days:** Modeling hybrid schedules and remote academic days.
2. **Carpooling:** Increasing car occupancy with a 10% route detour penalty ($D_{\text{detour}} = 1.10$).
3. **Institutional Bus / Shuttle Intervention:** Shifting private commuters while explicitly accounting for the shuttle's added diesel fuel emissions.

---

## 6. Author & Repository Information

- **Repository:** [ManojR-cs/CarboSync](https://github.com/ManojR-cs/CarboSync)
- **Project Name:** TraceTwin
- **Event:** Dayananda Sagar University Code Clash 2.0 (October 15–16, 2026)
