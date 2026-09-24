from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json
import sys

# Windows consoles often default to cp1252; the banner prints a non-ASCII arrow.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from core.runtime import LuminasRuntime
from security.local_only import LocalOnlyValidator
from security.validation import run_full_validation
from simulation.scenarios import ScenarioRunner

runtime = LuminasRuntime()

SCENARIOS = {
    "resident_returns_hot", "resident_returns_comfortable", "resident_leaves",
    "unknown_person", "temperature_sensor_failure", "cctv_offline", "ac_failure",
    "internet_unavailable", "conflicting_sensors", "duplicate_event", "malformed_event",
    "stale_temperature", "unknown_device",
}

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luminas Local Home — v0.6</title>
<style>
:root{
  --bg:#0a0d11; --panel:#10151b; --panel2:#0d1218; --line:#202933;
  --text:#edf2f5; --muted:#7f8a95; --soft:#aeb8c1; --ok:#7ee2ac;
  --warn:#e9c174; --bad:#f18c8c; --accent:#95b8ff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;min-height:100vh}
main{max-width:1500px;margin:0 auto;padding:28px}
header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:18px}
.eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:800}
.title{font-size:40px;letter-spacing:-.04em;font-weight:850;margin:7px 0 4px}
.sub{max-width:900px;color:var(--soft);line-height:1.55;font-size:14px}
.badge{border:1px solid #31523f;color:var(--ok);background:#0d1712;padding:9px 12px;border-radius:8px;font-size:11px;font-weight:800;letter-spacing:.06em;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}
.card{grid-column:span 12;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:17px;min-width:0}
.s3{grid-column:span 3}.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}.s12{grid-column:span 12}
.section{font-size:10px;color:var(--muted);font-weight:800;letter-spacing:.15em;text-transform:uppercase}
.metric{margin-top:7px;font-size:28px;font-weight:850;letter-spacing:-.03em}
.meta{font-size:11px;color:var(--muted);margin-top:6px}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.accent{color:var(--accent)}
.status-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:11px}
.status{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px}
.status span{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.status b{font-size:13px;display:block;margin-top:4px}
.device-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:12px}
.device{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:12px}
.device .id{font:700 12px ui-monospace,SFMono-Regular,Consolas,monospace}.device .type{font-size:11px;color:var(--muted);margin-top:3px}.device .state{font-size:12px;margin-top:8px;line-height:1.45}
.tag{display:inline-block;border:1px solid var(--line);padding:4px 6px;border-radius:7px;font:10px ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--soft);margin:2px}
.tag.twin{border-color:#2c4a6e;color:var(--accent)}
.activity{display:grid;gap:7px;margin-top:11px}.activity-row{display:grid;grid-template-columns:90px 1fr;gap:10px;align-items:start;border-bottom:1px solid #171e26;padding-bottom:7px}.activity-row:last-child{border-bottom:0}.activity-row .kind{font-size:10px;letter-spacing:.09em;color:var(--muted);font-weight:800}.activity-row .text{font-size:12px;line-height:1.45}
.timeline,.audit{font:11px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;max-height:300px;overflow:auto;color:#c2ccd4;margin-top:10px}
.controls{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}button{background:#141a21;color:var(--text);border:1px solid #2a333d;border-radius:8px;padding:9px 11px;font-weight:750;font-size:12px;cursor:pointer}button:hover{background:#181f27;border-color:#46525e}button.primary{border-color:#355d48;background:#0e1a14;color:var(--ok)}button.warn{border-color:#66532f;background:#1d180e;color:var(--warn)}button.danger{border-color:#603838;background:#1a1010;color:var(--bad)}button:disabled{opacity:.45;cursor:not-allowed}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}.node{border:1px solid var(--line);padding:8px 10px;border-radius:7px;background:var(--panel2);font:11px ui-monospace,SFMono-Regular,Consolas,monospace}.node.active{border-color:#355d48;color:var(--ok)}.arrow{color:#5e6872}
.note{font-size:11px;line-height:1.55;color:var(--muted);margin-top:10px}
.hero{border-color:#30455f;background:#0e141b}.hero .metric{font-size:20px;letter-spacing:-.01em}
.progress{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px}
.step{border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:9px 10px;font:10px ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--muted);letter-spacing:.08em}
.step b{display:block;font-size:12px;margin-top:3px;color:var(--soft)}
.step.active{border-color:#355d48;background:#0e1a14;color:var(--ok)}
.step.active b{color:var(--ok)}
.validation{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:11px}
.validation > div{border:1px solid var(--line);background:var(--panel2);padding:10px;border-radius:8px}
.validation b{font-size:16px}
footer{margin-top:18px;border-top:1px solid var(--line);padding-top:14px;color:#59636d;font-size:10px;line-height:1.55}
@media(max-width:1050px){.s3,.s4,.s5,.s6,.s7,.s8{grid-column:span 6}.status-grid{grid-template-columns:repeat(3,1fr)}.device-grid{grid-template-columns:repeat(2,1fr)}.progress{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){main{padding:15px}header{flex-direction:column}.s3,.s4,.s5,.s6,.s7,.s8,.s12{grid-column:span 12}.status-grid,.device-grid,.validation{grid-template-columns:1fr 1fr}.title{font-size:30px}.progress{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<main>
<header>
  <div>
    <div class="eyebrow">LUMINAS LOCAL HOME / SOFTWARE DIGITAL TWIN / v0.6</div>
    <div class="title">Local Intelligence for the Smart Home</div>
    <div class="sub">A local runtime coordinating simulated cameras, sensors, occupancy context, AC and lighting through hardware-independent interfaces. The devices shown here are Digital Twin components — not a claim of physical hardware connectivity.</div>
  </div>
  <div class="badge">● LOCAL PROCESS · INTERNET OFF</div>
</header>

<section class="grid">
  <div class="card s3"><div class="section">Brain</div><div class="metric ok">ONLINE</div><div class="meta">Local reasoning · deterministic decision engine</div></div>
  <div class="card s3"><div class="section">Occupancy</div><div class="metric" id="occupancy">—</div><div class="meta" id="occupancyMeta">—</div></div>
  <div class="card s3"><div class="section">Temperature</div><div class="metric" id="temp">—</div><div class="meta" id="tempMeta">—</div></div>
  <div class="card s3"><div class="section">Home Mode</div><div class="metric" id="mode">—</div><div class="meta" id="modeMeta">—</div></div>

  <div class="card s7 hero">
    <div class="section">Brain activity / structured explanation</div>
    <div class="metric accent" id="decision">Waiting for a local event</div>
    <div class="activity" id="activity"></div>
    <div class="note">This panel shows structured observations, context, rules and action/result facts. It does not expose hidden chain-of-thought and no cloud model is involved.</div>
  </div>

  <div class="card s5">
    <div class="section">System / privacy</div>
    <div class="status-grid">
      <div class="status"><span>Core network dependency</span><b class="ok">NONE</b></div>
      <div class="status"><span>Cloud dependency</span><b class="ok">NONE</b></div>
      <div class="status"><span>External API dependency</span><b class="ok">NONE</b></div>
      <div class="status"><span>External transmission</span><b class="ok" id="bytes">0 B</b></div>
      <div class="status"><span>Measurement scope</span><b>APPLICATION LEVEL</b></div>
    </div>
    <div class="note">Application-level measurement. Host-level packet capture is not claimed.</div>
  </div>

  <div class="card s12">
    <div class="section">Digital twin devices</div>
    <div class="device-grid" id="devices"></div>
  </div>

  <div class="card s12">
    <div class="section">Demo mode</div>
    <div class="note">Primary recording path: reset → resident returns → Brain decision chain → AC cooling. All values come from runtime state; the button state follows the actual backend demo status.</div>
    <div class="controls">
      <button class="primary" id="demoBtn" onclick="startDemo()">▶ RESIDENT RETURNS</button>
      <button onclick="runScenario('resident_returns_comfortable')">Comfortable Return</button>
      <button onclick="runScenario('resident_leaves')">Resident Leaves</button>
      <button onclick="runScenario('unknown_person')">Unknown Person</button>
      <button class="warn" onclick="runScenario('temperature_sensor_failure')">Temperature Failure</button>
      <button class="warn" onclick="runScenario('cctv_offline')">CCTV Offline</button>
      <button class="warn" onclick="runScenario('ac_failure')">AC Failure</button>
      <button class="warn" onclick="runScenario('stale_temperature')">Stale Sensor</button>
      <button onclick="runScenario('conflicting_sensors')">Conflicting Sensors</button>
      <button class="danger" onclick="runScenario('internet_unavailable')">External Route Block</button>
      <button onclick="resetHome()">Reset Home</button>
    </div>
    <div class="progress" id="progress"></div>
    <div class="meta" id="demoStatus">Demo state: IDLE</div>
  </div>

  <div class="card s6">
    <div class="section">Event timeline</div>
    <div class="timeline" id="timeline">Loading…</div>
  </div>

  <div class="card s6">
    <div class="section">Audit trail</div>
    <div class="audit" id="audit">Loading…</div>
  </div>

  <div class="card s6">
    <div class="section">Authenticated local mesh</div>
    <div class="timeline" id="mesh">Loading…</div>
  </div>

  <div class="card s6">
    <div class="section">Validation</div>
    <div class="validation" id="validation">
      <div><span class="meta">Unit tests</span><br><b id="valUnit">—</b></div>
      <div><span class="meta">Digital Twin demo</span><br><b id="valDemo">—</b></div>
      <div><span class="meta">Security / protocol</span><br><b id="valSec">—</b></div>
      <div><span class="meta">Failure scenarios</span><br><b id="valFailScen">—</b></div>
      <div><span class="meta">Local-only</span><br><b id="valLocal">—</b></div>
    </div>
    <div class="controls"><button id="valBtn" onclick="runValidation()">Run Full Validation</button><button onclick="runLocalOnly()">Local-Only Check</button></div>
    <div class="note" id="validationNote">Validation runs on demand only. Full validation executes the unit test suite, the primary Digital Twin demo, security/protocol checks, failure scenarios and application-level local-only validation.</div>
  </div>

  <div class="card s12">
    <div class="section">Brain → interface → device</div>
    <div class="flow">
      <span class="node">DIGITAL TWIN</span><span class="arrow">→</span>
      <span class="node">CAPABILITY CONTRACT</span><span class="arrow">→</span>
      <span class="node">LUMINAS BRAIN</span><span class="arrow">→</span>
      <span class="node">SAME CONTRACT</span><span class="arrow">→</span>
      <span class="node">FUTURE PHYSICAL ADAPTER</span>
    </div>
    <div class="note">Software-first architecture. Physical validation is the next stage. The v0.6 Brain does not depend on VirtualAC, VirtualCamera or vendor SDK names; hardware replacement belongs at the adapter boundary.</div>
  </div>
</section>

<footer>
  v0.6 is a software Digital Twin. Physical camera/sensor/AC/light integration is not claimed. Local-only validation is measured at Luminas application boundaries; this dashboard does not provide host-level packet capture or security certification.
</footer>
</main>
<script>
let demoBusy=false, valBusy=false;
const esc=s=>String(s??'').replace(/[&<>\\\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});return r.json()}
async function resetHome(){await post('/reset');await refresh()}
async function runScenario(name){const x=await post('/scenario/'+name);document.getElementById('validationNote').textContent=(x.result?.passed?'PASS: ':'FAIL: ')+(x.result?.summary||name);await refresh()}
async function startDemo(){if(demoBusy)return;demoBusy=true;const b=document.getElementById('demoBtn');b.disabled=true;b.textContent='● DEMO RUNNING…';await post('/demo');}
function applyDemo(d){
  const b=document.getElementById('demoBtn');
  b.disabled=!!d.running;
  if(!d.running){demoBusy=false;b.textContent='▶ RESIDENT RETURNS';}
  else{b.textContent='● DEMO RUNNING…';}
  document.getElementById('demoStatus').textContent='Demo state: '+d.demo_state+(d.last_error?' · '+d.last_error:'');
  const prog=document.getElementById('progress');
  prog.innerHTML=(d.stages||[]).map(s=>`<div class=\"step${s.active?' active':''}\">${s.num}<b>${esc(s.label)}</b></div>`).join('');
}
async function runValidation(){if(valBusy)return;valBusy=true;const btn=document.getElementById('valBtn');btn.disabled=true;btn.textContent='● VALIDATING…';try{const x=await post('/validation');const r=x.report;const set=(id,ok,txt)=>{const el=document.getElementById(id);el.textContent=txt;el.className=ok?'ok':'bad'};set('valUnit',r.unit_tests.passed,r.unit_tests.passed?r.unit_tests.run+' PASS':'FAIL');set('valDemo',r.primary_demo.passed,r.primary_demo.passed?'PASS':'FAIL');set('valSec',r.security.passed,r.security.checks_passed+'/'+r.security.checks_total);set('valFailScen',r.failure_scenarios.passed,r.failure_scenarios.checks_passed+'/'+r.failure_scenarios.checks_total);set('valLocal',r.local_only.passed,r.local_only.passed?'PASS':'FAIL');document.getElementById('validationNote').textContent='Full validation executed on an isolated fresh runtime: unit tests '+r.unit_tests.run+', protocol '+r.security.checks_total+', failure scenarios '+r.failure_scenarios.checks_total+'.'}finally{valBusy=false;btn.disabled=false;btn.textContent='Run Full Validation'}}
async function runLocalOnly(){const x=await post('/local-only');const r=x.validation;document.getElementById('validationNote').textContent=(r.passed?'PASS: ':'FAIL: ')+'application-level local-only check · external bytes '+r.application_external_transmission_bytes+' · import findings '+r.source_import_findings.length;}
function deviceCard(id,kind,state){let summary='';if(kind==='CCTV')summary=`${state.online?'ONLINE':'OFFLINE'} · local events only`;else if(kind==='TEMP_SENSOR')summary=`${state.available?'ONLINE':'UNAVAILABLE'} · ${state.value_c!=null?state.value_c.toFixed(1)+'°C':'no valid reading'}`;else if(kind==='MOTION_SENSOR')summary=`${state.online?'ONLINE':'OFFLINE'} · motion ${state.motion?'DETECTED':'CLEAR'}`;else if(kind==='DOOR_SENSOR')summary=`${state.online?'ONLINE':'OFFLINE'} · ${state.open?'OPEN':'CLOSED'}`;else if(kind==='AC')summary=`${state.online?'ONLINE':'OFFLINE'} · ${state.power?'ON':'OFF'} · target ${state.temperature_c.toFixed(0)}°C · room ${state.room_temperature_c.toFixed(1)}°C`;else if(kind==='LIGHT')summary=`${state.online?'ONLINE':'OFFLINE'} · ${state.power?'ON':'OFF'} · brightness ${state.brightness.toFixed(0)}%`;return `<div class=\"device\"><div class=\"id\">${esc(id)}</div><div class=\"type\">${esc(kind)} · ${esc(state.zone||state.location||'')}</div><div class=\"state\">${esc(summary)}</div><div style=\"margin-top:7px\"><span class=\"tag twin\">DIGITAL TWIN</span>${state.last_error?`<span class=\"tag bad\">${esc(state.last_error)}</span>`:''}</div></div>`}
function renderActivity(steps){document.getElementById('activity').innerHTML=(steps||[]).slice(-8).map(s=>`<div class=\"activity-row\"><div class=\"kind\">${esc(s.type)}</div><div class=\"text\">${esc(s.text)}</div></div>`).join('')||'<div class=\"meta\">No structured Brain activity yet.</div>'}
async function refresh(){try{const r=await fetch('/state');const x=await r.json();const s=x.home;const d=x.devices;const p=x.privacy;const n=x.network;document.getElementById('occupancy').textContent=s.occupied?'OCCUPIED':'EMPTY';document.getElementById('occupancyMeta').textContent=s.occupied?`confidence ${Math.round(s.occupancy_confidence*100)}% · ${s.occupancy_evidence.join(' + ')}`:'no resident evidence';document.getElementById('temp').textContent=s.temperature_available?s.temperature_c.toFixed(1)+'°C':'UNAVAILABLE';document.getElementById('tempMeta').textContent=s.temperature_available?'TEMP-01 · local reading':'TEMP-01 · safe hold';document.getElementById('mode').textContent=s.mode;document.getElementById('modeMeta').textContent=s.alerts.length?`ATTENTION · ${s.alerts.length} alert(s)`:'no active alerts';document.getElementById('decision').textContent=s.last_decision;renderActivity(s.decision_chain);document.getElementById('bytes').textContent=p.bytes_transmitted+' B';const cards=[['CCTV-01','CCTV',d.cctv],['TEMP-01','TEMP_SENSOR',d.temperature_sensor],['MOTION-01','MOTION_SENSOR',d.motion_sensor],['DOOR-01','DOOR_SENSOR',d.door],['AC-01','AC',d.ac],['LIGHT-01','LIGHT',d.lights]];document.getElementById('devices').innerHTML=cards.map(x=>deviceCard(x[0],x[1],x[2])).join('');document.getElementById('timeline').textContent=(x.events.recent_events||[]).slice(-24).map(e=>`${new Date(e.timestamp).toLocaleTimeString()} | ${e.type.toUpperCase().padEnd(24)} | ${e.source}`).join('\\n')||'No local events yet.';document.getElementById('audit').textContent=(x.audit||[]).slice(-30).map(e=>`${e.time} | ${(e.kind||'').padEnd(15)} | ${e.source.padEnd(10)} | ${e.action}`).join('\\n')||'No audit entries yet.';document.getElementById('mesh').textContent=(n.messages||[]).slice(-24).map(m=>`${m.timestamp} | ${m.sender} → ${m.recipient} | AUTH ✓ | ${m.payload.type}`).join('\\n')||'No authenticated local messages yet.';applyDemo(x.demo)}catch(e){}}
setInterval(refresh,500);refresh();
</script>
</body></html>'''


def state_payload():
    snap = runtime.state_snapshot()
    snap["demo_running"] = runtime.demo.running()
    snap["demo"] = runtime.demo.snapshot()
    return snap


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, code=200):
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path in ("/", "/state"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if path == "/" else "application/json; charset=utf-8")
            self.end_headers()
        else:
            self.send_error(404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            raw = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/state":
            self.send_json(state_payload())
        else:
            self.send_error(404)

    def do_POST(self):
        global runtime
        path = urlparse(self.path).path
        if path == "/reset":
            if not runtime.demo.running():
                runtime = LuminasRuntime()
            self.send_json({"ok": True})
            return
        if path == "/demo":
            started = runtime.demo.run_in_background()
            self.send_json({"ok": True, "started": started})
            return
        if path.startswith("/scenario/"):
            name = path.rsplit("/", 1)[-1]
            if name not in SCENARIOS or runtime.demo.running():
                self.send_json({"ok": False, "error": "scenario unavailable while demo runs" if runtime.demo.running() else "unknown scenario"}, code=400)
                return
            runner = ScenarioRunner(runtime)
            result = getattr(runner, name)()
            runtime = runner.runtime
            self.send_json({"ok": result.passed, "result": result.__dict__})
            return
        if path == "/validation":
            report = run_full_validation()
            self.send_json({"ok": report["ok"], "report": report})
            return
        if path == "/local-only":
            validation = LocalOnlyValidator().validate(runtime)
            self.send_json({"ok": validation["passed"], "validation": validation})
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print("Luminas Local Home v0.6 dashboard → http://127.0.0.1:8765 (localhost only)")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
