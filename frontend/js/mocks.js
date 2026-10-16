/**
 * TraceTwin — mocks.js
 * Static JSON fixtures for offline frontend testing.
 * Set USE_MOCKS = true in app.js to enable.
 */

const MOCK_DELAY_MS = 900; // simulate network latency

// ── Mock: Assessment Created ──────────────────────────────────
const MOCK_ASSESSMENT = {
  assessment_id: "ast_mock_01",
  assessment_name: "DSU Autumn 2026 Audit",
  campus_area: "North Gate Parking",
  reporting_period: "Academic Year 2026-27",
  annual_days: 200,
  status: "created",
  created_at: "2026-10-15T08:00:00Z"
};

// ── Mock: Human Verification Confirmed ───────────────────────
const MOCK_VERIFY_RESPONSE = {
  status: "confirmed",
  evidence_label: "Human-confirmed observation",
  verified_at: "2026-10-15T08:15:00Z"
};

// ── Mock: Baseline Emissions Calculation ──────────────────────
const MOCK_BASELINE = {
  assessment_id: "ast_mock_01",
  sample_size: 18,
  is_campus_projection: false,
  annual_days: 200,
  total_annual_vkt: 218400.0,
  total_annual_tonnes_co2: 24.62,
  evidence_label: "Derived calculation",
  category_breakdown: [
    {
      category: "Cars",
      daily_vehicles: 14,
      avg_one_way_km: 15.2,
      occupancy: 1.1,
      annual_vkt: 85120.0,
      emission_factor_kg_per_vkt: 0.145,
      annual_kg_co2: 12342.4,
      annual_tonnes_co2: 12.34
    },
    {
      category: "Motorcycles and scooters",
      daily_vehicles: 22,
      avg_one_way_km: 11.5,
      occupancy: 1.0,
      annual_vkt: 101200.0,
      emission_factor_kg_per_vkt: 0.035,
      annual_kg_co2: 3542.0,
      annual_tonnes_co2: 3.54
    },
    {
      category: "Buses and campus shuttles",
      daily_vehicles: 1,
      avg_one_way_km: 18.0,
      occupancy: 35.0,
      annual_vkt: 7200.0,
      emission_factor_kg_per_vkt: 0.850,
      annual_kg_co2: 6120.0,
      annual_tonnes_co2: 6.12
    },
    {
      category: "Other fuel-burning vehicles",
      daily_vehicles: 5,
      avg_one_way_km: 6.22,
      occupancy: 1.8,
      annual_vkt: 24880.0,
      emission_factor_kg_per_vkt: 0.078,
      annual_kg_co2: 1940.6,
      annual_tonnes_co2: 1.94
    }
  ]
};

// ── Mock: Scenario & AI Response ─────────────────────────────
const MOCK_SCENARIO = {
  baseline_tonnes_co2: 24.62,
  scenario_1_tonnes_co2: 19.70,  // 20% remote
  scenario_2_tonnes_co2: 18.44,  // 30% carpool
  scenario_3_tonnes_co2: 21.20,  // shuttle
  avoided_private_tonnes_co2: 9.82,
  added_shuttle_tonnes_co2: 3.40,
  net_savings_tonnes_co2: 6.42,
  fallback_activated: false,
  recommendations: [
    {
      rec_id: "REC_POOL_01",
      title: "Designated Carpool Parking Priority",
      difficulty: "Low",
      qualitative_rationale: "Single-occupancy cars represent over 50% of commute emissions. Providing reserved parking for verified carpools incentivises student and faculty ridesharing immediately with no infrastructure expenditure.",
      attached_savings_tonnes: 4.12,
      action_steps: [
        "Designate 15 front-row stalls near the main academic entrance for verified carpools.",
        "Implement a digital registration sticker system for verified two-passenger vehicles.",
        "Display real-time carpool slot availability on the campus app."
      ]
    },
    {
      rec_id: "REC_SHUTTLE_01",
      title: "High-Density Feeder Shuttle Corridors",
      difficulty: "Medium",
      qualitative_rationale: "Long-distance commuters travelling over 15 km contribute disproportionately to vehicle-kilometres. A high-capacity shuttle on key corridors consolidates these trips at significantly lower per-passenger emissions.",
      attached_savings_tonnes: 6.42,
      action_steps: [
        "Identify the top 3 high-density residential zones within 20 km of campus.",
        "Deploy a 40-seat CNG or EV shuttle on each corridor with two daily roundtrips.",
        "Subsidise semester passes at 60% of private fuel cost."
      ]
    },
    {
      rec_id: "REC_REMOTE_01",
      title: "Compressed Academic Timetabling",
      difficulty: "Low",
      qualitative_rationale: "One asynchronous learning day per fortnight reduces campus commute trips by approximately 10% per semester with zero infrastructure cost. Faculty scheduling software can automate the rotation.",
      attached_savings_tonnes: 2.46,
      action_steps: [
        "Pilot one asynchronous Friday per month for non-lab courses.",
        "Track attendance and engagement equivalency to confirm academic continuity.",
        "Scale to a full compressed 4-day academic week if pilot is successful."
      ]
    }
  ]
};

// ── Mock: Scenario with Negative Savings ─────────────────────
const MOCK_SCENARIO_NEGATIVE = {
  ...MOCK_SCENARIO,
  avoided_private_tonnes_co2: 2.10,
  added_shuttle_tonnes_co2: 4.80,
  net_savings_tonnes_co2: -2.70,
  scenario_3_tonnes_co2: 27.32
};

// ── Default DSU Survey Preset ─────────────────────────────────
const DSU_SAMPLE_PRESET = [
  { category: "Cars",                         daily_vehicles: 14, avg_one_way_km: 15.2, occupancy: 1.1 },
  { category: "Motorcycles and scooters",      daily_vehicles: 22, avg_one_way_km: 11.5, occupancy: 1.0 },
  { category: "Buses and campus shuttles",     daily_vehicles: 1,  avg_one_way_km: 18.0, occupancy: 35.0 },
  { category: "Other fuel-burning vehicles",   daily_vehicles: 5,  avg_one_way_km: 6.2,  occupancy: 1.8 }
];

// ── Emission Factors Table ────────────────────────────────────
const EMISSION_FACTORS = [
  {
    factor_id: "EF-CAR-IND-01",
    category: "Cars",
    value: 0.145,
    unit: "kg CO₂/veh-km",
    source: "MoRTH Road Transport Yearbook 2022–23 (India)",
    year: 2023,
    geography: "India (National Average)",
    note: "Petrol/CNG passenger car fleet average, tailpipe CO₂ only."
  },
  {
    factor_id: "EF-MOTO-IND-01",
    category: "Motorcycles and scooters",
    value: 0.035,
    unit: "kg CO₂/veh-km",
    source: "ARAI Emission Standards India BS-VI (2020)",
    year: 2020,
    geography: "India",
    note: "BS-VI two-wheeler petrol fleet average."
  },
  {
    factor_id: "EF-BUS-IND-01",
    category: "Buses and campus shuttles",
    value: 0.850,
    unit: "kg CO₂/veh-km",
    source: "IPCC 2006 Guidelines Vol. 2 (Diesel Road Transport)",
    year: 2006,
    geography: "Global / South Asia",
    note: "Diesel bus fleet. Tailpipe CO₂. Per-vehicle (not per-passenger)."
  },
  {
    factor_id: "EF-OTHER-IND-01",
    category: "Other fuel-burning vehicles",
    value: 0.078,
    unit: "kg CO₂/veh-km",
    source: "MoRTH / GHG Platform India (Auto-Rickshaw CNG proxy)",
    year: 2022,
    geography: "India Urban Fleet",
    note: "CNG auto-rickshaw proxy. Petrol three-wheelers may be 15–20% higher."
  }
];

// ── Simulated API call wrapper ────────────────────────────────
function mockApiCall(data, delayMs = MOCK_DELAY_MS) {
  return new Promise(resolve => setTimeout(() => resolve({ ok: true, data }), delayMs));
}
