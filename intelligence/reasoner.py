"""Deterministic structured explanation.

This layer produces safe, structured facts only: OBSERVATION / CONTEXT /
RULE / ACTION / RESULT. It never exposes hidden chain-of-thought and never
calls a cloud model. v0.6 intentionally stays a deterministic local reasoning
layer ("Local Reasoning / Deterministic Decision Engine"), not an LLM.
"""


class LocalReasoner:
    """Deterministic explanation layer; no LLM or network dependency."""

    COMFORT_THRESHOLD_C = 28.0

    def _trigger_label(self, trigger):
        return str(trigger or "local_event").replace("_", " ")

    def explain(self, state, trigger):
        """One-line deterministic summary used for the decision headline."""
        label = self._trigger_label(trigger)
        if not state.temperature_available:
            return f"{label}. Temperature is unavailable, so temperature-based automation is withheld."
        if not state.occupied:
            return f"{label}. Home is empty, so the safe empty-home state takes priority."
        if state.last_motion_minutes >= 15:
            return f"{label}. No movement for {state.last_motion_minutes:.0f} minutes, so energy saving takes priority."
        if state.guest_present:
            return f"{label}. Guest context is active, so the guest comfort profile applies."
        if state.temperature_c >= self.COMFORT_THRESHOLD_C:
            return f"{label}. Resident is present and indoor temperature is {state.temperature_c:.1f}°C, so cooling is appropriate."
        return f"{label}. Resident is present and temperature is comfortable, so cooling is not required."

    def structured_steps(self, state, trigger):
        """Structured OBSERVATION/CONTEXT/RULE facts for the dashboard."""
        steps = []
        if trigger == "resident_arrived":
            steps.append({"type": "OBSERVATION", "text": "Resident detected at front door."})
            steps.append({"type": "CONTEXT", "text": "Home appears occupied."})
        elif trigger == "resident_departed":
            steps.append({"type": "OBSERVATION", "text": "Resident departure observed."})
            steps.append({"type": "CONTEXT", "text": "Home appears empty."})
        elif trigger == "guest_arrived":
            steps.append({"type": "OBSERVATION", "text": "Guest detected."})
            steps.append({"type": "CONTEXT", "text": "Guest context is active."})
        elif trigger == "motion_detected":
            steps.append({"type": "OBSERVATION", "text": "Motion detected."})
            steps.append({"type": "CONTEXT", "text": f"Home occupancy = {'OCCUPIED' if state.occupied else 'EMPTY'}."})
        elif trigger == "sensor_unavailable":
            steps.append({"type": "OBSERVATION", "text": "Sensor fault reported."})
        else:
            steps.append({"type": "OBSERVATION", "text": f"Event received: {self._trigger_label(trigger)}."})

        if not state.temperature_available:
            steps.append({"type": "CONTEXT", "text": "Temperature sensor is unavailable."})
            steps.append({"type": "RULE", "text": "Temperature-based automation is withheld until a valid reading returns."})
            return steps

        steps.append({"type": "OBSERVATION", "text": f"Temperature = {state.temperature_c:.1f}°C."})

        if state.occupied and state.temperature_c >= self.COMFORT_THRESHOLD_C:
            steps.append({"type": "RULE", "text": "Temperature exceeds the comfort threshold."})
            steps.append({"type": "ACTION", "text": "Activate comfort mode."})
        elif state.occupied and state.last_motion_minutes >= 15:
            steps.append({"type": "RULE", "text": "No movement for the configured energy-save window."})
            steps.append({"type": "ACTION", "text": "Activate energy saving."})
        elif state.occupied and state.temperature_c <= self.COMFORT_THRESHOLD_C - 4.0:
            steps.append({"type": "RULE", "text": "Target temperature reached; comfort mode maintains the setpoint."})
        elif state.occupied:
            steps.append({"type": "RULE", "text": "Temperature is within the comfort range; cooling is not required."})
        else:
            steps.append({"type": "RULE", "text": "Home is empty; the safe empty-home state applies."})
        return steps
