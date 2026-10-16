"""Exercise the real frontend API adapter's mock image-upload branch."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendMockDetectionTests(unittest.TestCase):
    def test_mock_upload_has_no_sample_boxes_and_never_calls_backend(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        api_source = (ROOT / "frontend" / "js" / "api.js").as_posix()
        mock_source = (ROOT / "frontend" / "js" / "mocks.js").read_text(encoding="utf-8")
        self.assertNotIn("MOCK_CV_DETECTIONS", mock_source)
        script = r"""
const fs = require('fs');
global.window = { USE_MOCKS: true, CARBOSYNC_API_BASE: 'http://127.0.0.1:8000' };
global.mockApiCall = async () => ({ data: {} });
global.fetch = () => { throw new Error('mock image upload must not call the backend'); };
const source = fs.readFileSync(process.argv[1], 'utf8');
const api = new Function(source + '\nreturn API;')();
api.uploadImage('ast_test', null).then(result => {
  if (result.detections.length !== 0 || result.simulated !== true || result.inference_status !== 'simulated') {
    throw new Error('mock upload returned detections or ambiguous status');
  }
  process.stdout.write('mock upload returned zero boxes and explicit simulated status');
}).catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            [node, "-e", script, api_source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("zero boxes", result.stdout)

    def test_offline_boot_does_not_enable_mock_mode_implicitly(self):
        app_source = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.USE_MOCKS = false", app_source)
        self.assertNotIn("window.USE_MOCKS = !isOnline", app_source)

    def test_digital_twin_uses_backend_mode_profiles_and_exposes_animation_controls(self):
        app_source = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("representation?.scenarios?.[selectedKey]", app_source)
        self.assertIn("data-twin-play", app_source)
        self.assertIn("data-twin-pause", app_source)
        self.assertIn("data-twin-reset", app_source)
        self.assertIn('min="0.1" max="300" step="0.1"', app_source)
        css_source = (ROOT / "frontend" / "css" / "carbonsync.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css_source)
        self.assertIn("AppState.latestScenario = null", app_source)
        self.assertIn("The previous comparison is hidden until the new response arrives", app_source)

    def test_digital_twin_render_uses_successful_backend_flows_and_hides_stale_states(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        app_source = (ROOT / "frontend" / "js" / "app.js").as_posix()
        script = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('function renderScenarioTwin(');
const end = source.indexOf('function stopTwinAnimation(', start);
const renderer = new Function('safeText', 'window', source.slice(start, end) + '\nreturn renderScenarioTwin;')(
  value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  {matchMedia: () => ({matches:true})}
);
const result = {
  baseline:{annual_kg_co2:100},
  scenarios:{carpool:{annual_kg_co2:80}},
  assumptions:{carpool_occupancy:3},
  flow_representation:{
    basis:'Weekly round-trip commute-day activity.',
    baseline:{single_occupancy_car:4,carpool_vehicle:0,motorcycle:0,public_transport:0,shuttle:0,active_travel:0},
    scenarios:{carpool:{single_occupancy_car:2,carpool_vehicle:2,motorcycle:0,public_transport:0,shuttle:0,active_travel:0}}
  }
};
const html = renderer(result, {}, 'carpool', false, null);
const baselineTokens = (html.match(/data-route="baseline-/g) || []).length;
const proposedTokens = (html.match(/data-route="proposed-/g) || []).length;
if (baselineTokens !== 12 || proposedTokens !== 12) throw new Error(`expected normalized baseline/proposed symbols, got ${baselineTokens}/${proposedTokens}`);
for (const text of ['BASELINE · CURRENT COMMUTE MIX','PROPOSED · Carpool','data-twin-play','data-twin-pause','data-twin-reset','not a live campus traffic feed']) {
  if (!html.toLowerCase().includes(text.toLowerCase())) throw new Error(`missing visualization content: ${text}`);
}
const pending = renderer(result, {}, 'carpool', true, null);
if (pending.includes('twin-map')) throw new Error('pending scenario rendered stale twin');
process.stdout.write('backend-driven baseline/proposed flow renderer verified');
"""
        result = subprocess.run([node, "-e", script, app_source], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("baseline/proposed flow renderer verified", result.stdout)

    def test_scenario_comparison_uses_backend_reduction_values(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        app_source = (ROOT / "frontend" / "js" / "app.js").as_posix()
        script = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('function renderScenarioComparison(');
const end = source.indexOf('\nfunction ', start + 1);
const renderer = new Function('safeText', source.slice(start, end) + '\nreturn renderScenarioComparison;')(value => String(value ?? ''));
const scenario = {
  baseline: {annual_kg_co2: 100},
  scenarios: {carpool: {annual_kg_co2: 80, reduction_kg_co2: 17.5, reduction_percent: 17.5}},
  assumptions: {carpool_share: 0.5, carpool_occupancy: 3}
};
const html = renderer(scenario, 'carpool', false, null);
if (!html.includes('17.50 kg CO₂/year') || !html.includes('17.5%')) throw new Error('backend reduction values were not displayed');
process.stdout.write('backend reduction and percentage displayed');
"""
        result = subprocess.run([node, "-e", script, app_source], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("backend reduction and percentage displayed", result.stdout)

    def test_production_api_base_uses_same_origin_without_localhost_fallback(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        api_source = (ROOT / "frontend" / "js" / "api.js").as_posix()
        script = r"""
const fs = require('fs');
global.window = { USE_MOCKS: false, location: { hostname: 'carbon.example', port: '', origin: 'https://carbon.example' } };
global.document = { querySelector: () => null };
let requested = '';
global.fetch = async url => { requested = url; return { ok: true, json: async () => ({ campaign: null }) }; };
const source = fs.readFileSync(process.argv[1], 'utf8');
const api = new Function(source + '\nreturn API;')();
api.getCampaign().then(() => {
  if (requested !== 'https://carbon.example/api/demo/campaigns/current') throw new Error('production API URL did not use same origin');
  process.stdout.write('same-origin production API URL verified');
}).catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            [node, "-e", script, api_source], cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("same-origin production API URL", result.stdout)


if __name__ == "__main__":
    unittest.main()
