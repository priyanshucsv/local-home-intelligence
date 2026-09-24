# Demo Guide — Luminas Local Home v0.6

## 1. Startup

```bash
python dashboard.py
```

Open:

```text
http://127.0.0.1:8765
```

- Browser size: **1600×900 or larger**, hide bookmarks bar, close other tabs.
- Recording resolution: **1920×1080** (or 2560×1440 at 2× DPR). 30 fps is enough.
- No terminal windows need to be visible. No files need editing. No restarts.

The dashboard is idle on load (validation shows `READY`); nothing runs until you click.

## 2. Primary recording — 30–90 second social version

**You never reset manually. The RESIDENT RETURNS button resets the Digital Twin
and runs the full deterministic sequence (~12–14 s total).**

| Time | Shot | What to do / what appears |
|---|---|---|
| 0–3 s | **1 · Title** | Show the header: `LUMINAS LOCAL HOME` / `Local Intelligence for the Smart Home` / `SOFTWARE DIGITAL TWIN · v0.6` |
| 3–7 s | **2 · Empty home** | Cards show `OCCUPANCY EMPTY`, `TEMPERATURE 31.4°C`, `AC OFF`, `LIGHTS OFF`; privacy shows `CORE NETWORK DEPENDENCY NONE`, `CLOUD DEPENDENCY NONE`, `EXTERNAL API DEPENDENCY NONE`, `EXTERNAL TRANSMISSION 0 B`, `MEASUREMENT SCOPE APPLICATION LEVEL` |
| 7 s | **3 · Start** | Click **▶ RESIDENT RETURNS** — button becomes `● DEMO RUNNING…` (disabled) and the progress strip lights up |
| 7–9 s | **4 · Door** | Timeline: `DOOR_OPENED`; door card `OPEN` |
| 9–11 s | **5 · Camera** | Timeline: `RESIDENT_DETECTED`; CCTV-01 card `DIGITAL TWIN · ONLINE` |
| 11–13 s | **6 · Context** | Timeline: `OCCUPANCY_CONFIRMED`; occupancy `OCCUPIED · confidence 97% · DOOR + CCTV_RESIDENT` |
| 13–15 s | **7 · Brain** | Brain activity shows `OBSERVATION Resident detected at front door.` / `CONTEXT Home appears occupied.` / `OBSERVATION Temperature = 31.4°C.` / `RULE Temperature exceeds the comfort threshold.` / `ACTION Activate comfort mode.` |
| 15–17 s | **8 · Action** | AC card `ON · target 24°C`, light `ON`; timeline shows the commands and results |
| 17–26 s | **9 · Cooling** | Temperature card steps down `31.4 → 31.1 → 30.8 → … → 24.0` labeled **SIMULATED ROOM TEMPERATURE** (values are live runtime state); demo state reaches `COMPLETE` |
| 26–31 s | **10 · Privacy** | Show the privacy panel values above with the note `Application-level measurement. Host-level packet capture is not claimed.` |
| 31–38 s | **11 · Failure** | Click **Temperature Failure** → TEMP-01 `UNAVAILABLE`, Brain shows `Temperature-based automation withheld`, audit shows the security event |
| 38–45 s | **12 · Hardware path** | Show the flow strip: `DIGITAL TWIN → CAPABILITY CONTRACT → LUMINAS BRAIN → SAME CONTRACT → FUTURE PHYSICAL ADAPTER` with the caption `Software-first architecture. Physical validation is the next stage.` |
| 45–50 s | **13 · Final frame** | `LUMINAS LOCAL HOME` / `v0.6 SOFTWARE DIGITAL TWIN` / `PHYSICAL VALIDATION: NEXT STAGE` |

## 3. Longer technical demo — 2–4 minutes

1. Intro and honesty statement (software Digital Twin, no hardware claimed)
2. Empty home + privacy panel
3. Primary demo end-to-end (above)
4. Failure tour, one at a time: CCTV Offline, AC Failure, Stale Sensor,
   Conflicting Sensors, External Route Block — narrate what each proves
5. Validation: click **Run Full Validation** and show the five categories
   (Unit tests / Digital Twin demo / Security protocol / Failure scenarios /
   Local-only) all PASS
6. Architecture strip + hardware bridge explanation
7. Final frame with the disclaimer below

## 4. Failure demonstrations

Each button runs its scenario on a fresh deterministic runtime:

- **Temperature Failure** — TEMP-01 unavailable; automation withheld; nothing invented
- **CCTV Offline** — no resident detection is fabricated; door/motion still work
- **AC Failure** — comfort decision made, `AC command → FAILED` visible + audited, lights still work
- **Stale Sensor** — freshness window exceeded; data invalidated
- **Unknown Person** — security attention; resident comfort automation NOT triggered
- **Conflicting Sensors** — occupancy evidence conflict surfaced as attention
- **External Route Block** — route blocked; external bytes stay 0

## 5. What each event means

```text
DOOR_OPENED            entry sensor fired at the front door
RESIDENT_DETECTED      local camera reports a known resident identity
OCCUPANCY_CONFIRMED    context engine combined the evidence
TEMPERATURE_CHANGED    fresh local reading from TEMP-01
COMFORT_MODE_ACTIVATED decision engine crossed the 28°C threshold
AC_POWER_ON            authenticated local command to AC-01 accepted
AC_TARGET_SET          setpoint 24°C accepted
LIGHT_ON               lighting command accepted
SIMULATED COOLING      Digital Twin thermal model stepping toward target
```

## 6. Claim discipline while narrating

Say "simulated room temperature", never "the room cooled down".
Say "Digital Twin AC", never "the AC". Say "application-level measurement",
never "no network traffic". Do not say "production ready", "physically proven"
or "real AC control".

## 7. Exact final disclaimer

> Luminas Local Home v0.6 is a software Digital Twin. All devices shown are
> simulated through hardware-independent capability contracts. Local-only
> claims are measured at the application level only. Physical hardware has
> not been connected or validated; physical validation is the next stage.

## 8. Suggested narration (30–60 s)

> "This is Luminas — a local-first home intelligence runtime. Everything you
> see runs in one local process: no cloud, no external APIs, zero bytes sent
> out. A resident returns to a 31-degree home. The door, camera and motion
> sensors are simulated Digital Twin devices speaking the same authenticated
> local protocol a real device will use. The Brain confirms occupancy, sees
> the temperature, and decides locally: comfort mode, AC on, target 24, lights
> on. The room cools gradually — simulated, honestly labeled. And when a
> sensor fails, the Brain doesn't invent data: it withholds automation and
> says so. The architecture is hardware-ready; physical validation is the
> next stage."
