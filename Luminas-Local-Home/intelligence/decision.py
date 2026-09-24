from devices.contracts import ClimateController, LightController


class DecisionEngine:
    """Deterministic local policy engine using hardware-independent contracts."""

    COMFORT_THRESHOLD = 28.0
    ENERGY_SAVE_MINUTES = 15.0
    RESIDENT_AC_TARGET = 24.0
    GUEST_AC_TARGET = 25.0

    def __init__(self, bus, state, ac: ClimateController, lights: LightController, audit, reasoner):
        self.bus = bus
        self.state = state
        self.ac = ac
        self.lights = lights
        self.audit = audit
        self.reasoner = reasoner

    def handle(self, event):
        trigger = event["type"]
        steps = self.reasoner.structured_steps(self.state, trigger)
        self.state.last_decision = self.reasoner.explain(self.state, trigger)
        self.audit.record("REASONING", self.state.last_decision, kind="DECISION")

        if not self.state.temperature_available and trigger in {"resident_arrived", "temperature_changed", "guest_arrived", "sensor_unavailable"}:
            steps.append({"type": "ACTION", "text": "Withhold temperature-based automation until a valid reading returns."})
            self.state.mode = "SAFE_HOLD" if self.state.occupied else "EMPTY"
            self.state.record_decision(steps)
            self.audit.record("DECISION", "TEMPERATURE_AUTOMATION_WITHHELD", kind="DECISION")
            return

        if not self.state.occupied:
            self._empty_home_policy(steps)
        elif self.state.last_motion_minutes >= self.ENERGY_SAVE_MINUTES:
            self._energy_saving_policy(steps)
        elif self.state.guest_present:
            self._guest_policy(steps)
        else:
            self._resident_policy(steps)

        self.state.record_decision(steps)

    def _result(self, steps, text, ok):
        steps.append({"type": "RESULT", "text": text})
        return ok

    def _empty_home_policy(self, steps):
        self.state.mode = "EMPTY"
        steps.append({"type": "RULE", "text": "Home is empty; return comfort devices to a safe idle state."})
        self._result(steps, f"Turn off AC: {'SUCCESS' if self.ac.turn_off() else 'FAILED'}", not self.state.devices["ac"]["power"])
        self._result(steps, f"Turn off lights: {'SUCCESS' if self.lights.turn_off() else 'FAILED'}", not self.state.devices["lights"]["power"])
        self.audit.record("DECISION", "EMPTY_HOME_SAFE_STATE", kind="DECISION")

    def _energy_saving_policy(self, steps):
        self.state.mode = "ENERGY_SAVING"
        steps.append({"type": "RULE", "text": f"No movement for {self.state.last_motion_minutes:.0f} minutes; enable energy saving."})
        self._result(steps, f"AC off: {'SUCCESS' if self.ac.turn_off() else 'FAILED'}", not self.state.devices["ac"]["power"])
        self._result(steps, f"Lights off: {'SUCCESS' if self.lights.turn_off() else 'FAILED'}", not self.state.devices["lights"]["power"])
        self.audit.record("DECISION", f"ENERGY_SAVING minutes={self.state.last_motion_minutes:.0f}", kind="DECISION")

    def _guest_policy(self, steps):
        self.state.mode = "GUEST"
        steps.append({"type": "RULE", "text": "Guest context active; use guest comfort profile."})
        lights_ok = self.lights.turn_on()
        self._result(steps, f"Lights on: {'SUCCESS' if lights_ok else 'FAILED'}", lights_ok)
        if self.state.temperature_c >= self.COMFORT_THRESHOLD:
            ac_on = self.ac.turn_on()
            ac_target = self.ac.set_temperature(self.GUEST_AC_TARGET) if ac_on else False
            self._result(steps, f"AC on: {'SUCCESS' if ac_on else 'FAILED'}", ac_on)
            self._result(steps, f"AC target 25°C: {'SUCCESS' if ac_target else 'FAILED'}", ac_target)
        else:
            ac_off = self.ac.turn_off()
            self._result(steps, f"AC remains off: {'SUCCESS' if ac_off else 'FAILED'}", ac_off)
        self.audit.record("DECISION", "GUEST_COMFORT_MODE", kind="DECISION")

    def _resident_policy(self, steps):
        self.state.mode = "OCCUPIED"
        lights_ok = self.lights.turn_on()
        self._result(steps, f"Lights on: {'SUCCESS' if lights_ok else 'FAILED'}", lights_ok)
        ac_target = float(self.state.devices["ac"]["temperature_c"])
        should_cool = self.state.temperature_c >= self.COMFORT_THRESHOLD or (self.state.devices["ac"]["power"] and self.state.temperature_c > ac_target)
        if should_cool:
            steps.append({"type": "RULE", "text": "Temperature exceeds the active comfort target; continue cooling toward the AC setpoint." if self.state.temperature_c < self.COMFORT_THRESHOLD else "Temperature exceeds comfort threshold; activate comfort mode."})
            self.audit.record("DECISION", "COMFORT_MODE_ACTIVATED", kind="DECISION")
            ac_on = self.ac.turn_on()
            target_ok = self.ac.set_temperature(self.RESIDENT_AC_TARGET) if ac_on else False
            self._result(steps, f"AC power on: {'SUCCESS' if ac_on else 'FAILED'}", ac_on)
            self._result(steps, f"AC target 24°C: {'SUCCESS' if target_ok else 'FAILED'}", target_ok)
            self.state.mode = "COMFORT" if ac_on and target_ok else "COMFORT_DEGRADED"
        else:
            at_target = self.state.devices["ac"]["power"] and self.state.temperature_c <= ac_target + 0.05
            if at_target:
                steps.append({"type": "RULE", "text": "Target temperature reached; comfort mode maintains the setpoint."})
                self.audit.record("DECISION", "COMFORT_MAINTAINED target_reached=true", kind="DECISION")
                self.state.mode = "COMFORT"
            else:
                ac_off = self.ac.turn_off()
                self._result(steps, f"AC remains off: {'SUCCESS' if ac_off else 'FAILED'}", ac_off)
                self.audit.record("DECISION", "RESIDENT_NORMAL_MODE", kind="DECISION")
                self.state.mode = "OCCUPIED"
