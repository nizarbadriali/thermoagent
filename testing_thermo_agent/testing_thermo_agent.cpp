#include <DHT.h>

#define DHT_PIN  4
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("DHT22 Test");
  dht.begin();
}

void loop() {
  float temp_c = dht.readTemperature();
  float temp_f = dht.readTemperature(true);
  float humidity = dht.readHumidity();

  if (isnan(temp_c) || isnan(humidity)) {
    Serial.println("Failed to read from DHT22!");
  } else {
    Serial.printf("Temp: %.1f C / %.1f F  Humidity: %.1f%%\n", 
                  temp_c, temp_f, humidity);
  }

  delay(3000);
}