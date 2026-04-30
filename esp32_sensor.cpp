// ESP32 sensor node for the thermo-agent.
//
// Reads a DHT22 every PUBLISH_INTERVAL_MS and publishes JSON to MQTT for the
// Raspberry Pi agent (thermo_agent.py) to consume.
//
// Topic:   home/thermo/sensor
// Payload: {"temp_c":22.4,"humidity":41.2}
//
// Libraries (install via Arduino Library Manager or PlatformIO):
//   - "DHT sensor library" by Adafruit
//   - "Adafruit Unified Sensor"
//   - "PubSubClient" by Nick O'Leary
//
// Wiring (DHT22):
//   VCC  -> 3V3
//   DATA -> GPIO 4   (with 10kΩ pull-up to 3V3)
//   GND  -> GND
//
// If using the Arduino IDE, rename this file to esp32_sensor.ino and place it
// in a folder named esp32_sensor/.

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// ---- Config ------------------------------------------------------------------

static const char* WIFI_SSID     = "YOUR_WIFI_SSID";
static const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

static const char* MQTT_HOST     = "192.168.1.10";   // Raspberry Pi IP
static const uint16_t MQTT_PORT  = 1883;
static const char* MQTT_USER     = "";               // "" if broker is open
static const char* MQTT_PASS     = "";
static const char* MQTT_CLIENTID = "esp32-thermo-sensor";

static const char* TOPIC_SENSOR  = "home/thermo/sensor";
static const char* TOPIC_STATUS  = "home/thermo/sensor/status";  // LWT

#define DHT_PIN   4
#define DHT_TYPE  DHT22

static const uint32_t PUBLISH_INTERVAL_MS = 30000;   // 30s — Pi marks stale at 180s
static const uint32_t SENSOR_WARMUP_MS    = 2000;    // DHT22 needs ~2s after power

// ---- Globals -----------------------------------------------------------------

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// ---- Wi-Fi -------------------------------------------------------------------

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("[wifi] connecting to %s ", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
    Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf(" ok, ip=%s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println(" FAILED, will retry");
  }
}

// ---- MQTT --------------------------------------------------------------------

void connectMQTT() {
  if (mqtt.connected()) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(60);
  Serial.printf("[mqtt] connecting to %s:%u ", MQTT_HOST, MQTT_PORT);
  // Last Will: if the ESP32 drops, broker publishes "offline" so anyone
  // watching status knows. The Pi agent already fails safe on staleness, so
  // this is just for visibility.
  bool ok = mqtt.connect(
      MQTT_CLIENTID,
      strlen(MQTT_USER) ? MQTT_USER : nullptr,
      strlen(MQTT_PASS) ? MQTT_PASS : nullptr,
      TOPIC_STATUS, 1, true, "offline");
  if (ok) {
    Serial.println("ok");
    mqtt.publish(TOPIC_STATUS, "online", true);
  } else {
    Serial.printf("FAILED rc=%d\n", mqtt.state());
  }
}

// ---- Sensor + publish --------------------------------------------------------

void publishReading() {
  float t = dht.readTemperature();   // °C
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.println("[dht] read failed (NaN)");
    return;
  }

  char payload[64];
  // Pi accepts temp_c or temp_f; sending native DHT22 units (°C).
  int n = snprintf(payload, sizeof(payload),
                   "{\"temp_c\":%.1f,\"humidity\":%.1f}", t, h);
  if (n <= 0 || n >= (int)sizeof(payload)) {
    Serial.println("[mqtt] payload format error");
    return;
  }

  if (mqtt.publish(TOPIC_SENSOR, payload, false)) {
    Serial.printf("[mqtt] tx %s %s\n", TOPIC_SENSOR, payload);
  } else {
    Serial.println("[mqtt] publish failed");
  }
}

// ---- Arduino entrypoints -----------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n[boot] thermo sensor node");
  dht.begin();
  delay(SENSOR_WARMUP_MS);
  connectWiFi();
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected())             connectMQTT();
  mqtt.loop();

  static uint32_t lastPublish = 0;
  uint32_t now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;
    if (mqtt.connected()) publishReading();
  }

  delay(50);
}
