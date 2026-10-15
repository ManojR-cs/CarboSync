# Master Verification & Test Plan — TraceTwin

**Document Type:** Formal Test Suite & Quality Assurance Protocol  
**Current Stage:** Planning & Pre-Hackathon Verification  
**Last Updated:** October 15, 2026  
**Auditor:** TraceTwin Quality Assurance Lead  

> [!IMPORTANT]
> **Execution Status Notice:** In compliance with the Code Clash 2.0 hackathon code-writing constraints, **no functional code has been authored or executed prior to the hackathon**.
> 
> All test cases below are designated as **`Planned` / `Untested`**. During the active hackathon, the team will execute these tests against the live code, logging actual outputs and marking them `Passed` or `Failed` only upon physical execution.

---

## 1. Test Suite Overview & Coverage Matrix

| Test Suite ID | Functional Area | Test Cases | Objective |
| :---: | :--- | :---: | :--- |
| **TS-IMG** | Image Upload & Ingestion | 3 | Validate file format, size limits, and corrupt buffer rejection. |
| **TS-DET** | Computer Vision Detection | 3 | Verify YOLOv8n inference, category mapping, and confidence filtering. |
| **TS-HUM** | Human Verification Loop | 4 | Test box deletion, reclassification, manual drawing, and confirmation. |
| **TS-DUP** | Photo Duplication & Overlap | 2 | Ensure multiple photos are not naively summed as daily traffic. |
| **TS-CALC** | Hand-Calculated Carbon Benchmarks | 3 | Numerically verify $\text{VKT} \times EF$ against hand-computed ground truth. |
| **TS-UNIT** | Unit Invariants & Isolation | 2 | Confirm isolation between vehicle-km and passenger-km factors. |
| **TS-INP** | Boundary & Error Handling | 3 | Test zero values, negative distances, and missing input fields. |
| **TS-SCEN** | Digital Twin Scenario Modeling | 4 | Verify remote days, carpool detours, and added shuttle emissions. |
| **TS-GUARD**| Guarded AI & Fallback Gate | 3 | Test AI number stripping, schema enforcement, and fallback activation. |
| **TS-PRIV** | Privacy & Data Minimization | 2 | Verify zero PII storage, locality scrubbing, and temp file cleanup. |
| **TS-E2E** | End-to-End User Journey | 1 | Complete walkthrough of live 4-minute demonstration script. |

---

## 2. Test Suite Specifications

### 2.1 TS-IMG: Image Upload & Ingestion Validation

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-IMG-01** | **Valid JPEG Image Upload**<br>*Precondition:* Active assessment created. | Standard $1920 \times 1080$ JPEG photo of parking lot (3.2 MB). | File accepted (HTTP 200); assigned `image_id`; saved to volatile upload directory. | `Planned` | *Pending live test execution* |
| **T-IMG-02** | **Oversized Image Rejection**<br>*Precondition:* Active assessment created. | JPEG file of size 14.8 MB (exceeds 10 MB limit). | Upload rejected (HTTP 400/413); user alert: "File exceeds 10 MB limit"; buffer cleared. | `Planned` | *Pending live test execution* |
| **T-IMG-03** | **Corrupt / Non-Image MIME Rejection**<br>*Precondition:* Active assessment created. | Renamed text file (`malicious.exe` renamed to `car.jpg`). | MIME validation fails (HTTP 400); alert: "Invalid image format"; file deleted from disk. | `Planned` | *Pending live test execution* |

---

### 2.2 TS-DET: Computer Vision & Class Reconciliation

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-DET-01** | **Standard Vehicle Class Mapping**<br>*Precondition:* YOLOv8n model loaded in memory. | Test parking photo containing 10 cars, 4 motorcycles, and 1 bus. | Model identifies objects; extracts normalized boxes; maps to `Cars`, `Motorcycles and scooters`, `Buses and campus shuttles`. | `Planned` | *Pending live test execution* |
| **T-DET-02** | **Low-Confidence Filtering**<br>*Precondition:* Model confidence threshold set to 0.35. | Image with distant background clutter or blurry shadows. | Detections with confidence $< 0.35$ are suppressed from initial canvas rendering. | `Planned` | *Pending live test execution* |
| **T-DET-03** | **Zero Detection Handling**<br>*Precondition:* Model loaded. | Photo of an empty paved parking lot with 0 vehicles. | Inference completes (HTTP 200); returns 0 boxes; alert: "0 vehicles detected. You may add boxes manually." | `Planned` | *Pending live test execution* |

---

### 2.3 TS-HUM: Human Verification & Correction Loop

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-HUM-01** | **False-Positive Box Deletion**<br>*Precondition:* Image loaded with bounding boxes. | User clicks on a misidentified shadow (tagged as Motorcycle) and hits Delete. | Box removed from UI canvas; vehicle count decrements by 1; `is_deleted: true` staged. | `Planned` | *Pending live test execution* |
| **T-HUM-02** | **Class Reclassification (Auto-Rickshaw)**<br>*Precondition:* Detections rendered. | User selects a box misidentified as `Truck` and changes dropdown to `Other fuel-burning vehicles`. | Box color updates; category mapped to "Other fuel-burning vehicles"; summary counts reflect change. | `Planned` | *Pending live test execution* |
| **T-HUM-03** | **Manual Bounding Box Addition**<br>*Precondition:* Canvas in interactive mode. | User clicks and drags over an unspotted motorcycle in a shaded corner. | New box rendered; category set to `Motorcycles and scooters`; `is_manually_added: true`. | `Planned` | *Pending live test execution* |
| **T-HUM-04** | **Verification Confirmation & Lock**<br>*Precondition:* Human edits complete. | User clicks "Confirm Verification". | Counts locked; persisted to database under `parking_observations` with tag `[Human-confirmed observation]`. | `Planned` | *Pending live test execution* |

---

### 2.4 TS-DUP: Duplicate & Repeated Photo Handling

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-DUP-01** | **Consecutive Snapshot Warning**<br>*Precondition:* Photo already uploaded for Lot A at 10:00 AM. | User uploads a second photo for Lot A captured at 11:30 AM. | System prompts user: "Is this a time-series audit of Lot A or a separate lot?"; disables naive auto-summing. | `Planned` | *Pending live test execution* |
| **T-DUP-02** | **Photo Counts Isolated from Daily Commuters**<br>*Precondition:* Photo verified with 80 cars. | User navigates to Baseline Emissions dashboard. | Baseline remains dependent on Commute Activity inputs; photo counts **not** injected into daily $N_k$. | `Planned` | *Pending live test execution* |

---

### 2.5 TS-CALC: Hand-Calculated Carbon Benchmarks

The following hand-calculated test cases serve as absolute numerical benchmarks for verifying the deterministic engine:

#### Benchmark Case 1 (Single Mode — Cars)
- **Inputs:**
  - $N_{\text{car}} = 50 \text{ vehicles/day}$
  - $D_{\text{car}} = 15.0 \text{ km/trip}$
  - Return multiplier $= 2$
  - Commuting days $Y = 200 \text{ days/year}$
  - Emission factor $EF_{\text{car}} = 0.150 \text{ kg } CO_2/\text{veh-km}$
- **Hand Calculation:**
  $$\text{Annual VKT} = 50 \times 15.0 \times 2 \times 200 = 300,000 \text{ km/year}$$
  $$\text{Annual kg } CO_2 = 300,000 \times 0.150 = 45,000 \text{ kg } CO_2/\text{year}$$
  $$\text{Annual Tonnes } CO_2 = 45,000 / 1000 = \mathbf{45.000 \text{ tonnes } CO_2/\text{year}}$$

#### Benchmark Case 2 (Multi-Modal Campus Cohort)
- **Inputs:**
  - Cars: $N=20, D=12.0\text{ km}, EF=0.150$ $\rightarrow \text{VKT}=96,000\text{ km} \rightarrow \text{Emissions}=14,400\text{ kg } CO_2$
  - Motorcycles: $N=60, D=10.0\text{ km}, EF=0.035$ $\rightarrow \text{VKT}=240,000\text{ km} \rightarrow \text{Emissions}=8,400\text{ kg } CO_2$
  - Buses: $N=2, D=20.0\text{ km}, EF=0.900$ $\rightarrow \text{VKT}=16,000\text{ km} \rightarrow \text{Emissions}=14,400\text{ kg } CO_2$
  - Other: $N=5, D=8.0\text{ km}, EF=0.080$ $\rightarrow \text{VKT}=16,000\text{ km} \rightarrow \text{Emissions}=1,280\text{ kg } CO_2$
- **Hand Calculation:**
  $$\text{Total VKT} = 96,000 + 240,000 + 16,000 + 16,000 = \mathbf{368,000 \text{ km/year}}$$
  $$\text{Total Emissions} = 14,400 + 8,400 + 14,400 + 1,280 = 38,480 \text{ kg } CO_2$$
  $$\text{Total Baseline} = 38,480 / 1000 = \mathbf{38.480 \text{ tonnes } CO_2/\text{year}}$$

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-CALC-01** | **Single Mode Verification**<br>*Precondition:* Engine initialized. | Benchmark Case 1 parameters ($N=50, D=15, Y=200, EF=0.150$). | Engine returns exactly $300,000 \text{ VKT}$ and $\mathbf{45.000 \text{ tonnes } CO_2}$ (tolerance: $\pm 0.001$). | `Planned` | *Pending live test execution* |
| **T-CALC-02** | **Multi-Modal Cohort Verification**<br>*Precondition:* Engine initialized. | Benchmark Case 2 multi-modal parameters. | Engine returns exactly $368,000 \text{ VKT}$ and $\mathbf{38.480 \text{ tonnes } CO_2}$ (tolerance: $\pm 0.001$). | `Planned` | *Pending live test execution* |
| **T-CALC-03** | **Zero Commute Boundary**<br>*Precondition:* Engine initialized. | All daily vehicle counts $N_k = 0$. | Engine returns exactly $0 \text{ VKT}$ and $\mathbf{0.000 \text{ tonnes } CO_2}$ without divide-by-zero exceptions. | `Planned` | *Pending live test execution* |

---

### 2.6 TS-UNIT: Unit Invariants & Isolation

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-UNIT-01** | **Vehicle-km vs Passenger-km Isolation**<br>*Precondition:* Schema validator active. | Pass a passenger-km factor ($0.040 \text{ kg } CO_2/\text{pass-km}$) directly to a vehicle VKT calculation. | System throws Type/Validation error; blocks calculation; enforces `kg CO2/veh-km` factor. | `Planned` | *Pending live test execution* |
| **T-UNIT-02** | **Occupancy Conversion Integrity**<br>*Precondition:* Commuter headcount input = 100. | Passenger mode shift: 100 persons shifting to carpooling at occupancy $O=2.5$. | Engine derives exactly $40 \text{ vehicles}$; computes VKT using $40 \times D$, NOT $100 \times D$. | `Planned` | *Pending live test execution* |

---

### 2.7 TS-INP: Boundary & Error Handling

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-INP-01** | **Negative Distance Rejection**<br>*Precondition:* Commute form active. | User enters average distance $D_{\text{car}} = -12.5 \text{ km}$. | Request rejected (HTTP 422); UI alert: "Distance must be greater than 0.0 km". | `Planned` | *Pending live test execution* |
| **T-INP-02** | **Negative Operating Days Rejection**<br>*Precondition:* Assessment setup form. | User enters academic days $Y = -20$. | Request rejected (HTTP 422); UI alert: "Academic days must be an integer between 1 and 366". | `Planned` | *Pending live test execution* |
| **T-INP-03** | **Small Sample Warning ($n < 20$)**<br>*Precondition:* Commute survey import. | User imports survey data with sample size $n = 14$. | Data accepted, but prominent Amber badge rendered: "Sample Size: n=14 (< 20). Sample-based baseline only." | `Planned` | *Pending live test execution* |

---

### 2.8 TS-SCEN: Digital Twin Scenario Modeling

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-SCEN-01** | **Fewer Commute Days (Remote Schedule)**<br>*Precondition:* Benchmark 1 baseline ($45.0 \text{ t } CO_2$). | Remote schedule slider set to $20\%$ ($P_{\text{remote}} = 0.20$). | Scenario emissions evaluate to $36.000 \text{ t } CO_2$; Net Avoided evaluates to $\mathbf{9.000 \text{ t } CO_2}$. | `Planned` | *Pending live test execution* |
| **T-SCEN-02** | **Carpooling Detour Penalty Verification**<br>*Precondition:* 20 solo drivers shift to carpool ($O=2.0$). | Baseline distance $D=10 \text{ km}$, Detour penalty $D_{\text{detour}} = 1.10$. | Pooled distance calculated as $11.0 \text{ km}$; 10 pooled cars $\times 11.0 \text{ km}$; net savings reflect detour overhead. | `Planned` | *Pending live test execution* |
| **T-SCEN-03** | **Shuttle Added Fuel Combustion (Positive Net Savings)**<br>*Precondition:* 60 car commuters shift to 2 shuttle routes. | Avoided car emissions $= 24.0 \text{ t } CO_2$; Added shuttle diesel burn $= 10.5 \text{ t } CO_2$. | Net Avoided computes as $24.0 - 10.5 = \mathbf{13.500 \text{ t } CO_2}$; added emissions explicitly itemized on UI. | `Planned` | *Pending live test execution* |
| **T-SCEN-04** | **Shuttle Negative Net Savings Handling**<br>*Precondition:* Only 4 car commuters shift, but 2 large diesel shuttles run all day. | Avoided car emissions $= 1.8 \text{ t } CO_2$; Added shuttle diesel burn $= 8.5 \text{ t } CO_2$. | Net Avoided computes as $1.8 - 8.5 = \mathbf{-6.700 \text{ t } CO_2}$; UI highlights Amber/Red warning: "Shuttle adds net emissions". | `Planned` | *Pending live test execution* |

---

### 2.9 TS-GUARD: Guarded AI & Fallback Gate

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-GUARD-01**| **AI Hallucinated Number Stripping**<br>*Precondition:* LLM API mock returns a response containing fake numbers ("Saves 82.4 tonnes and $5,000"). | Raw LLM output string with unapproved numbers. | Interceptor strips unapproved numbers or rejects output; injects deterministic value ($9.0 \text{ t } CO_2$). | `Planned` | *Pending live test execution* |
| **T-GUARD-02**| **AI Timeout (>4000ms) & Deterministic Fallback**<br>*Precondition:* Mock network delay injected ($5000 \text{ ms}$). | User requests AI policy explanation. | Proxy aborts outbound call at 4000ms; activates deterministic rule-based catalog; UI displays `"Rule-based plan (AI unavailable)"`. | `Planned` | *Pending live test execution* |
| **T-GUARD-03**| **Zero PII in Outbound Prompt**<br>*Precondition:* Assessment contains test student register notes. | Backend constructs prompt payload for LLM API. | Outbound JSON payload inspected; contains zero names, roll numbers, or exact addresses; only aggregate metrics. | `Planned` | *Pending live test execution* |

---

### 2.10 TS-PRIV: Privacy & Data Minimization

| Test ID | Test Title & Preconditions | Input Data | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-PRIV-01** | **Database PII Prohibition Audit**<br>*Precondition:* SQLite database populated during test runs. | SQL query: `SELECT * FROM sqlite_master` and table inspection. | Confirmed: Zero columns exist for `student_name`, `student_id`, `street_address`, or `biometrics`. | `Planned` | *Pending live test execution* |
| **T-PRIV-02** | **Volatile Upload Cleanup**<br>*Precondition:* 5 images uploaded and verified. | User triggers "Purge Session" or terminates server. | Uploaded image buffers deleted from local disk; only numerical verified counts remain in database. | `Planned` | *Pending live test execution* |

---

### 2.11 TS-E2E: End-to-End User Journey Walkthrough

| Test ID | Test Title & Preconditions | Scripted Sequence | Expected Result | Status | Actual Result |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **T-E2E-01** | **Complete Live 4-Minute Hackathon Demo**<br>*Precondition:* Clean database, server running on laptop. | 1. Create Assessment "DSU North Gate 2026"<br>2. Upload parking snapshot image<br>3. Review detections in Canvas; delete 1 false positive, reclassify 1 auto-rickshaw<br>4. Confirm verification<br>5. Enter commute survey inputs ($n=18$)<br>6. View baseline emissions chart with evidence tags<br>7. Adjust Carpooling and Shuttle sliders<br>8. View guarded AI recommendations with attached deterministic numbers<br>9. Simulate network cutoff; verify rule-based fallback renders within 4s. | Full user journey executes flawlessly in under 4 minutes with zero uncaught exceptions, zero console errors, and clean evaluator presentation. | `Planned` | *Pending live test execution* |
