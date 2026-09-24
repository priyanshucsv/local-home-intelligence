class VirtualHouse:
    def __init__(self, runtime):
        self.runtime = runtime

    def show_state(self):
        state = self.runtime.state.snapshot()
        p = self.runtime.privacy.snapshot()
        n = self.runtime.network.snapshot()
        ac = state["devices"]["ac"]
        lights = state["devices"]["lights"]
        print("\n========== LUMINAS LOCAL HOME / DIGITAL TWIN ==========")
        print(f"Mode:           {state['mode']}")
        print(f"Occupied:       {state['occupied']} ({state['occupancy_confidence']:.0%})")
        print(f"Temperature:    {state['temperature_c']:.1f}°C {'AVAILABLE' if state['temperature_available'] else 'UNAVAILABLE'}")
        print(f"AC:             {'ON' if ac['power'] else 'OFF'} | target {ac['temperature_c']:.1f}°C | cooling {ac['cooling']}")
        print(f"Lights:         {'ON' if lights['power'] else 'OFF'} | brightness {lights['brightness']:.0f}%")
        print(f"Door:           {'OPEN' if state['devices']['door']['open'] else 'CLOSED'}")
        print(f"Alerts:         {', '.join(state['alerts']) if state['alerts'] else 'NONE'}")
        print(f"Mesh messages:  {len(n['messages'])} authenticated")
        print(f"Privacy:        {p['status']} | external bytes={p['bytes_transmitted']} | scope={p['measured_scope']}")
        print("=======================================================\n")
