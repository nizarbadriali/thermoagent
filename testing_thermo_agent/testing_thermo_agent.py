import time
try:
    from gpiozero import OutputDevice
    relay = OutputDevice(17, active_high=False)
    REAL_GPIO = True
except Exception:
    REAL_GPIO = False
    print("[mock] no GPIO found, running in simulation mode")

def reflex_agent(temperature):
    if temperature >= 80:
        return "cool"
    elif temperature <= 68:
        return "heat"
    else:
        return "off"

def set_relay(state):
    if REAL_GPIO:
        if state == "on":
            relay.on()
        else:
            relay.off()

def run_test(fake_temp, label):
    print(f"\n--- TEST: {label} ---")
    print(f"Fake temperature: {fake_temp}°F")
    action = reflex_agent(fake_temp)
    print(f"Agent decision: {action}")
    
    if action in ("cool", "heat"):
        print("Relay → ON (you should hear a click)")
        set_relay("on")
        time.sleep(3)  # relay stays on for 3 seconds
        print("Relay → OFF")
        set_relay("off")
        time.sleep(1)
    else:
        print("Relay → stays OFF")
        set_relay("off")

def main():
    print("=== THERMO AGENT RELAY TEST ===\n")
    
    # Test 1 — temperature too high, should trigger relay ON
    run_test(85, "HIGH TEMP — should trigger relay")
    time.sleep(2)
    
    # Test 2 — temperature too low, should trigger relay ON
    run_test(60, "LOW TEMP — should trigger relay")
    time.sleep(2)
    
    # Test 3 — temperature in range, relay should stay OFF
    run_test(72, "NORMAL TEMP — relay should stay OFF")
    
    print("\n=== TEST COMPLETE ===")
    print("If relay clicked on tests 1 and 2 and stayed silent on test 3 — system works!")

if __name__ == "__main__":
    main()