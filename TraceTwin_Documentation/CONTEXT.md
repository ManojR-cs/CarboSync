# Developer & AI Assistant Context Guide — TraceTwin

**Document Type:** Context & Invariant Engineering Guide  
**Target Audience:** Human Developers, Team Members, and AI Coding Assistants  
**Last Updated:** October 15, 2026  

---

## 1. Project Purpose & Core Directive

TraceTwin is a campus commute-emissions intelligence platform built for the **Dayananda Sagar University Code Clash 2.0 Hackathon (October 15–16, 2026)**.

The platform answers three fundamental questions for campus decision-makers:
1. *What commute-related tailpipe emissions can we estimate from the empirical evidence available to a university?*
2. *Which operational or transit interventions (remote days, carpooling, shuttles) will verifiably reduce those emissions?*
3. *How can the system transparently disclose its methodology, factor provenance, and data limitations without greenwashing or speculation?*

### The Core Architectural Principle
> **AI may detect objects and explain results, but deterministic calculations and documented emission factors must control all numerical emissions claims.**

---

## 2. Critical Hackathon Constraints (Strict Enforcement)

1. **All application source code must be authored during the active 48-hour hackathon window.**
2. **Pre-built templates, starter projects, or pre-written code repositories are strictly prohibited by event rules.**
3. **Role of AI Assistants:**
   - AI assistants must act as collaborative pair-programmers during the hackathon.
   - AI assistants must **never generate pre-built application files, executable scripts, or hidden starter templates before the official hackathon start**.
   - When writing technical specifications, describe architectures in prose, JSON contracts, and Markdown tables rather than generating functional implementations.
4. **Status Honesty Rule:**
   - Use the status labels consistently:
     - `Confirmed`: Explicitly decided by the team.
     - `Proposed`: Recommended design, awaiting live implementation.
     - `Needs verification`: Dependent on external validation, tests, or sources.
     - `Out of scope`: Deliberately excluded from the MVP.
     - `Implemented`: ONLY when verified code exists in the active workspace.
     - `Tested`: ONLY when a test has actually executed with documented output.
   - **Never claim a feature is implemented or tested merely because it appears in the design.**

---

## 3. Team Capability Profile & Working Conventions

- **Team Composition:** 4 members, primarily beginner to intermediate developers.
- **Strengths:** Python logic, computer vision pipeline experimentation, and AI-assisted debugging.
- **Areas Needing Scaffolding:** Frontend state management, Canvas-to-API coordinate synchronization, error boundary handling.
- **Collaboration Style:** 4 parallel workstreams governed by a shared, frozen REST API contract, overseen by a dedicated Integration Owner.
- **Simplicity Mandate:** Favor clean, readable, well-commented native Python and vanilla JavaScript over complex frameworks, heavy bundlers, or distributed microservices.

---

## 4. Non-Negotiable Invariants & Methodology Rules

Any AI assistant or developer modifying this repository must uphold these mathematical, scientific, and architectural invariants:

### Invariant 1: Separation of Evidence Streams
Under no circumstances should the number of vehicles detected in a parking photograph be added to survey-derived commuter counts or attendance records.
- **Parking Photographs:** Point-in-time snapshot observations of physical occupancy. Useful for CV demonstration and spot-checking, but **not** a direct count of unique daily commuters.
- **Attendance Registers:** Proof of campus presence on a given calendar day; **does not** reveal the mode of transit taken.
- **Commute Surveys:** Source of mode-share distributions, average trip distances, and vehicle occupancies. Must be treated as a sample ($n < 20$); must **not** be silently extrapolated to the entire university without explicit, labeled assumptions.

### Invariant 2: Vehicle-Kilometres vs. Passenger-Kilometres
- Never multiply passenger counts by vehicle-kilometre emission factors.
- Baseline calculations must use **Vehicle-Kilometres Traveled (VKT)**:
  $$\text{VKT}_k = N_k \times D_k \times 2 \times Y$$
  $$\text{Emissions}_k (\text{kg } CO_2) = \text{VKT}_k \times EF_k$$
- If an input is expressed in passenger count, it must first be divided by the verified vehicle occupancy ratio ($O_k$) to derive vehicle count before applying a vehicle-kilometre emission factor.

### Invariant 3: Scope Boundaries
- **Four Supported Categories (and ONLY four):**
  1. `Cars` (Internal combustion passenger cars)
  2. `Motorcycles and scooters` (Two-wheelers)
  3. `Buses and campus shuttles` (Institutional buses)
  4. `Other fuel-burning vehicles, including auto-rickshaws` (Three-wheelers, light commercial vans)
- **Baseline Exclusions:**
  - `Electric Vehicles (EVs)`: Excluded from baseline (grid carbon intensity and charging dynamics out of scope for MVP).
  - `Walking & Cycling`: Excluded (zero tailpipe emissions; active transport is excluded from vehicular accounting).
- **Metric Scope:** Direct tailpipe greenhouse gas emissions ($\text{kg } CO_2$ or metric tonnes $t CO_2$). Upstream Well-to-Tank (WTT) and vehicle manufacturing lifecycle emissions are excluded.

### Invariant 4: Digital Twin Rebound & Added Emissions
- In **Scenario 3 (Bus/Shuttle Intervention)**, the system **must calculate and display the added fuel emissions of the operating shuttles** ($VKT_{\text{shuttle}} \times EF_{\text{shuttle}}$).
- The system must display negative net savings honestly if an intervention increases campus emissions due to low occupancy.

### Invariant 5: Guarded AI Isolation & Fallback
- The Generative AI API is strictly a **qualitative policy copywriter and ranker**.
- The LLM must receive **zero numerical calculation authority**.
- The LLM must receive **zero Personally Identifiable Information (PII)** (no names, no student IDs, no exact addresses, no raw photos).
- The backend must intercept and validate the LLM's JSON output. If the response violates the schema, hallucinates unapproved numbers, or times out (>4000ms), the system must seamlessly engage the **deterministic rule-based fallback** labeled:  
  `"Rule-based plan (AI unavailable)"`.

---

## 5. Mandatory Evidence Tagging System

Every numerical claim, table cell, and metric card in the frontend must display one of the six approved evidence tags:

| Evidence Tag | Strict Definition |
| :--- | :--- |
| `[Direct observation]` | Measured directly by automated instrumentation or raw computer vision detection. |
| `[Human-confirmed observation]` | A direct observation that has been audited, modified, or confirmed by a human reviewer. |
| `[Survey-reported value]` | Data collected via commuter questionnaire or sample survey. |
| `[Source-derived value]` | An established constant or emission factor drawn from verified published literature. |
| `[Assumption]` | An unverified or estimated operational parameter adopted for modeling purposes. |
| `[Derived calculation]` | A mathematical output resulting from deterministic calculations on the above inputs. |

---

## 6. Privacy & Data Minimization Rules

- **Zero Student PII in Database:** The SQLite database must never store student names, registration numbers, exact residential street addresses, or raw ID card scans.
- **Locality-Level Minimization:** Commute origins must be stored and processed exclusively at the neighborhood, ward, or postal code level (e.g., "Banashankari 3rd Stage", "Indiranagar").
- **Third-Party Data Transfer:** Never send unminimized addresses or individual attendance records to external mapping or AI providers.

---

## 7. How Future AI Assistants Must Behave

When prompted to assist the TraceTwin team during the hackathon:
1. **Never Invent Implementations:** Do not tell the user that an API, component, or algorithm is already built or tested when it is not in the active workspace.
2. **Never Generate Code Prior to Kickoff:** Maintain the documentation-only boundary until the hackathon officially commences.
3. **Verify Units on Every Change:** Whenever proposing a formula or endpoint, explicitly specify units (e.g., `km`, `kg CO2/km`, `tonnes CO2`).
4. **Enforce Graceful Degradation:** Always implement the deterministic fallback path alongside any external API integration.
5. **Keep It Simple:** Avoid recommending microservices, Docker clusters, Redux, Tailwind build pipelines, or cloud databases. Stick to the local, beginner-friendly stack (FastAPI, SQLite, Vanilla HTML/CSS/JS, Chart.js, YOLOv8n CPU).
