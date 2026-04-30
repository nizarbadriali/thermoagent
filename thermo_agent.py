"""Thermostat agent — Raspberry Pi side.

Subscribes to a DHT22 reading published by an ESP32 over MQTT and toggles a
single-channel 5V relay (call-for-cool OR call-for-heat, set by HVAC_MODE).

Expected MQTT payload (JSON), published by the ESP32:
    {"temp_c": 22.4, "humidity": 41.2}        # DHT22 native units, OR
    {"temp_f": 72.3, "humidity": 41.2}
"""

import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from threading import Event, Lock
from typing import Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/thermo/sensor")

HVAC_MODE = os.getenv("HVAC_MODE", "cool").lower()
RELAY_PIN = int(os.getenv("RELAY_PIN", "17"))
# Most cheap blue 5V relay boards are active-LOW (pin LOW = relay energized).
RELAY_ACTIVE_HIGH = os.getenv("RELAY_ACTIVE_HIGH", "false").lower() == "true"

SETPOINT_F = float(os.getenv("SETPOINT_F", "75"))
HYSTERESIS_F = float(os.getenv("HYSTERESIS_F", "1.5"))

MIN_OFF_SECONDS = int(os.getenv("MIN_OFF_SECONDS", "300"))
STALE_AFTER_SECONDS = int(os.getenv("STALE_AFTER_SECONDS", "180"))
LOOP_INTERVAL = 5

try:
    from gpiozero import OutputDevice
except ImportError:
    OutputDevice = None


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def should_call(mode: str, temp_f: float, setpoint_f: float,
                hysteresis_f: float, currently_on: bool) -> bool:
    """Hysteresis band: cool turns ON at setpoint+H, OFF at setpoint-H; heat is mirrored."""
    if mode == "cool":
        return temp_f > (setpoint_f - hysteresis_f) if currently_on \
            else temp_f >= (setpoint_f + hysteresis_f)
    if mode == "heat":
        return temp_f < (setpoint_f + hysteresis_f) if currently_on \
            else temp_f <= (setpoint_f - hysteresis_f)
    raise ValueError(f"HVAC_MODE must be 'cool' or 'heat', got {mode!r}")


def parse_payload(raw: bytes) -> Optional[float]:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logging.warning("non-JSON payload: %r", raw[:60])
        return None
    if "temp_f" in msg:
        return float(msg["temp_f"])
    if "temp_c" in msg:
        return c_to_f(float(msg["temp_c"]))
    logging.warning("payload missing temp_c/temp_f: %r", msg)
    return None


class Relay:
    def __init__(self, pin: int, active_high: bool):
        self._lock = Lock()
        self._on = False
        self._last_change = time.monotonic()
        if OutputDevice is None:
            self._dev = None
            logging.warning("gpiozero unavailable — relay in MOCK mode (not on a Pi?)")
        else:
            self._dev = OutputDevice(pin, active_high=active_high, initial_value=False)

    def is_on(self) -> bool:
        return self._on

    def seconds_since_change(self) -> float:
        return time.monotonic() - self._last_change

    def set(self, on: bool) -> bool:
        with self._lock:
            if on == self._on:
                return False
            if self._dev is not None:
                (self._dev.on if on else self._dev.off)()
            self._on = on
            self._last_change = time.monotonic()
            return True

    def close(self):
        self.set(False)
        if self._dev is not None:
            self._dev.close()


@dataclass
class SensorState:
    temp_f: Optional[float] = None
    last_msg_at: float = 0.0


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if HVAC_MODE not in ("cool", "heat"):
        sys.exit(f"HVAC_MODE must be 'cool' or 'heat', got {HVAC_MODE!r}")

    relay = Relay(RELAY_PIN, RELAY_ACTIVE_HIGH)
    state = SensorState()
    stop = Event()

    def on_connect(client, _ud, _flags, rc, _props=None):
        if rc == 0:
            logging.info("MQTT connected %s:%s, subscribing %s",
                         MQTT_HOST, MQTT_PORT, MQTT_TOPIC)
            client.subscribe(MQTT_TOPIC, qos=1)
        else:
            logging.error("MQTT connect failed rc=%s", rc)

    def on_message(_client, _ud, msg):
        temp_f = parse_payload(msg.payload)
        if temp_f is None:
            return
        state.temp_f = temp_f
        state.last_msg_at = time.monotonic()
        logging.info("rx %s -> %.1f°F", msg.topic, temp_f)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="thermo_agent_pi")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    def shutdown(*_):
        logging.info("shutdown signal — relay OFF")
        stop.set()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logging.info("agent up — mode=%s setpoint=%.1f°F hysteresis=±%.1f°F",
                 HVAC_MODE, SETPOINT_F, HYSTERESIS_F)
    try:
        while not stop.is_set():
            now = time.monotonic()
            stale = state.last_msg_at == 0 or (now - state.last_msg_at) > STALE_AFTER_SECONDS

            if stale:
                if relay.is_on():
                    logging.warning("sensor stale (>%ds) — failing safe to OFF",
                                    STALE_AFTER_SECONDS)
                    relay.set(False)
                stop.wait(LOOP_INTERVAL)
                continue

            want_on = should_call(HVAC_MODE, state.temp_f, SETPOINT_F,
                                  HYSTERESIS_F, relay.is_on())

            # Compressor protection: don't restart within MIN_OFF_SECONDS of stopping.
            if want_on and not relay.is_on() \
                    and relay.seconds_since_change() < MIN_OFF_SECONDS:
                logging.debug("want ON but in min-off window (%ds left)",
                              MIN_OFF_SECONDS - int(relay.seconds_since_change()))
            elif relay.set(want_on):
                logging.info("relay -> %s (temp %.1f°F)",
                             "ON" if want_on else "OFF", state.temp_f)

            stop.wait(LOOP_INTERVAL)
    finally:
        relay.close()
        client.loop_stop()
        client.disconnect()
        logging.info("stopped cleanly")


if __name__ == "__main__":
    main()
