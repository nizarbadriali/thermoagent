WELCOME TO YOUR THERMO BUDDY

A simple reflex AI agent that monitors room temperature and controls a fan via relay using a Raspberry Pi 5 and ESP32.

---

## How It Works

The agent applies three rules every 30 seconds:
- Temp ≥ 80°F → fan ON
- Temp ≤ 68°F → fan ON  
- Otherwise → fan OFF

No memory. No learning. Pure reflex logic.

---

## Hardware

| Component | Role |
|---|---|
| Raspberry Pi 5 | Agent brain |
| ESP32 + DHT22 | Wireless sensor node |
| 5V Relay | GPIO-controlled switch |
| 12V DC Fan + Adapter | Physical actuator |

---

## Files

| File | Runs On | Purpose |
|---|---|---|
| thermo_agent.py | Pi | Main agent loop |
| esp32_sensor.cpp | ESP32 | Reads DHT22, publishes over MQTT |
| dht22_test.cpp | ESP32 | Sensor signal test |
| test_relay.py | Pi | Relay and fan signal test |

---

## Testing

Tested in isolated layers before full system integration:

1. **Layer 1** — Flash dht22_test.cpp, verify Serial Monitor shows temperature readings
2. **Layer 2** — Run test_relay.py on Pi, verify relay clicks and fan spins
3. **Layer 3** — Run full system, warm DHT22 by hand, verify fan responds

---

## Safety

Hysteresis, compressor min-off time, stale sensor failsafe, and clean shutdown on SIGINT/SIGTERM.

---

## Roadmap

**Phase 1 (current)** — ESP32 + DHT22 on breadboard, Pi + relay module

**Phase 2** — Custom RP2040 + Si7021 PCB replacing breadboard, wired I2C to Pi, USB-C programming

**Phase 3** — RF integrated PCB with onboard WiFi, fully wireless standalone sensor node