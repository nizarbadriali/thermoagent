import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ECOBEE_KEY = os.environ["ECOBEE_KEY"]
THERMOSTAT_ID = os.environ["THERMOSTAT_ID"]

def get_temperature():
    """Read real temp from your Ecobee thermostat."""
    response = requests.get(
        "https://api.ecobee.com/thermostat",
        headers={"Authorization": f"Bearer {ECOBEE_KEY}"},
        params={"thermostatId": THERMOSTAT_ID}
    )
    return response.json()["temperature"]

def set_hvac(mode):
    """Tell your Ecobee to switch modes — 'cool', 'heat', or 'off'."""
    requests.post(
        "https://api.ecobee.com/thermostat",
        headers={"Authorization": f"Bearer {ECOBEE_KEY}"},
        json={"thermostatId": THERMOSTAT_ID, "hvacMode": mode}
    )

def reflex_agent(temperature):
    """No memory, just rules mapping percept to action."""
    if temperature >= 80:
        return "cool"
    elif temperature <= 68:
        return "heat"
    else:
        return "off"

def main():
    """Agent loop will run forever on standby, and it will check every 5m."""
    print("Home Thermostat Agent — Standing by...\n")
    while True:
        temp = get_temperature()
        action = reflex_agent(temp)
        set_hvac(action)
        print(f"Temp: {temp}°F  →  HVAC set to: {action}")
        time.sleep(300)

if __name__ == "__main__":
    main()