#include <Arduino.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <HX711.h>
#include <Preferences.h>
#include <Wire.h>
#include <WiFi.h>
#include <time.h>

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Set these values before uploading from Arduino IDE.
constexpr char FRESHBOX_WIFI_SSID[] = "VishwasiPhone";
constexpr char FRESHBOX_WIFI_PASSWORD[] = "vishwas@123";
constexpr char FRESHBOX_API_BASE_URL[] = "http://172.20.10.2:8000";
constexpr char FRESHBOX_BATCH_ID[] = "74845293-ee42-4778-baad-1336c0331798";
constexpr char FRESHBOX_DEVICE_ID[] = "freshbox-esp32-01";

// Load cell calibration factor (from your 177g calibration test: 110260 counts / 177g = 622.94 counts/g)
constexpr float FRESHBOX_HX711_CALIBRATION_FACTOR = 622.94f;

#define FRESHBOX_HCSR04_ENABLED 1

namespace
{

  constexpr uint8_t DHT_PIN = 4;
  constexpr uint8_t MQ135_PIN = 34;
  constexpr uint8_t HX711_DOUT_PIN = 19;
  constexpr uint8_t HX711_SCK_PIN = 18;
  constexpr uint8_t HCSR04_TRIG_PIN = 5;
  constexpr uint8_t HCSR04_ECHO_PIN = 23;
  constexpr uint8_t OLED_SDA_PIN = 21;
  constexpr uint8_t OLED_SCL_PIN = 22;
  constexpr uint8_t DHT_TYPE = DHT22;
  constexpr uint8_t OLED_ADDRESS = 0x3C;

  constexpr uint32_t READING_INTERVAL_MS = 30000;
  constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;
  constexpr uint32_t HTTP_TIMEOUT_MS = 5000;
  constexpr uint32_t MQ_WARMUP_INTERVAL_MS = 60000;
  constexpr uint32_t HCSR04_TIMEOUT_US = 25000;
  constexpr float FOOD_PRESENT_DISTANCE_CM = 13.0f;
  constexpr float FOOD_PRESENCE_HYSTERESIS_CM = 0.5f;
  constexpr float HX711_CALIBRATION_MASS_G = 177.0f;
  constexpr uint16_t ADC_MAX_VALUE = 4095;
  constexpr long GMT_OFFSET_SECONDS = 0;
  constexpr int DAYLIGHT_OFFSET_SECONDS = 0;

  DHT dht(DHT_PIN, DHT_TYPE);
  HX711 loadCell;
  Preferences calibrationStorage;
  Adafruit_SSD1306 display(128, 64, &Wire, -1);

  bool dhtInitialized = false;
  bool hx711Initialized = false;
  bool hx711CalibrationReady = false;
  bool calibrationStorageReady = false;
  bool emptyTareConfirmed = false;
  bool oledInitialized = false;
  bool timeInitialized = false;
  bool wifiAttempted = false;
  bool previousWifiConnected = false;
  uint32_t bootTimeMs = 0;
  uint32_t lastReadingMs = 0;
  uint32_t lastWifiAttemptMs = 0;
  uint32_t lastTimeAttemptMs = 0;

  struct SensorReading
  {
    float temperatureC = NAN;
    float humidityPct = NAN;
    int gasRaw = -1;
    float weightG = NAN;
    float distanceCm = NAN;
    bool temperatureValid = false;
    bool humidityValid = false;
    bool gasRawValid = false;
    bool weightValid = false;
    bool distanceValid = false;
  };

  enum class FoodPresence
  {
    Unknown,
    Absent,
    Present,
  };

  FoodPresence foodPresence = FoodPresence::Unknown;

  bool finiteInRange(float value, float minimum, float maximum)
  {
    return isfinite(value) && value >= minimum && value <= maximum;
  }

  bool getTimestamp(char *buffer, size_t bufferSize)
  {
    if (!timeInitialized || buffer == nullptr || bufferSize == 0)
    {
      return false;
    }

    const time_t now = time(nullptr);
    if (now < 1700000000)
    {
      return false;
    }

    struct tm utcTime{};
    if (gmtime_r(&now, &utcTime) == nullptr)
    {
      return false;
    }

    return strftime(buffer, bufferSize, "%Y-%m-%dT%H:%M:%SZ", &utcTime) > 0;
  }

  void connectWifi()
  {
    if (WiFi.status() == WL_CONNECTED || strlen(FRESHBOX_WIFI_SSID) == 0)
    {
      return;
    }

    const uint32_t now = millis();
    if (wifiAttempted && now - lastWifiAttemptMs < WIFI_RETRY_INTERVAL_MS)
    {
      return;
    }

    wifiAttempted = true;
    lastWifiAttemptMs = now;
    Serial.printf("Connecting to Wi-Fi SSID '%s'\n", FRESHBOX_WIFI_SSID);
    WiFi.begin(FRESHBOX_WIFI_SSID, FRESHBOX_WIFI_PASSWORD);
  }

  void initializeTime()
  {
    if (WiFi.status() != WL_CONNECTED || timeInitialized)
    {
      return;
    }

    const uint32_t now = millis();
    if (lastTimeAttemptMs != 0 && now - lastTimeAttemptMs < 60000)
    {
      return;
    }
    lastTimeAttemptMs = now;

    configTime(GMT_OFFSET_SECONDS, DAYLIGHT_OFFSET_SECONDS, "pool.ntp.org", "time.nist.gov");
    struct tm timeInfo{};
    timeInitialized = getLocalTime(&timeInfo, 10000);
    Serial.println(timeInitialized ? "Clock synchronized." : "Clock sync pending.");
  }

  float readDistanceCm(bool &valid)
  {
    valid = false;
#if FRESHBOX_HCSR04_ENABLED
    digitalWrite(HCSR04_TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(HCSR04_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(HCSR04_TRIG_PIN, LOW);

    const unsigned long duration =
        pulseIn(HCSR04_ECHO_PIN, HIGH, HCSR04_TIMEOUT_US);
    if (duration == 0)
    {
      return NAN;
    }

    const float distanceCm = static_cast<float>(duration) * 0.0343f / 2.0f;
    valid = finiteInRange(distanceCm, 2.0f, 400.0f);
    return valid ? distanceCm : NAN;
#else
    return NAN;
#endif
  }

  SensorReading readSensors()
  {
    SensorReading reading;

    if (dhtInitialized)
    {
      reading.temperatureC = dht.readTemperature();
      reading.humidityPct = dht.readHumidity();
      reading.temperatureValid =
          finiteInRange(reading.temperatureC, -40.0f, 85.0f);
      reading.humidityValid =
          finiteInRange(reading.humidityPct, 0.0f, 100.0f);
    }

    const int adcValue = analogRead(MQ135_PIN);
    reading.gasRaw = adcValue;
    reading.gasRawValid =
        adcValue >= 0 &&
        adcValue <= ADC_MAX_VALUE &&
        (millis() - bootTimeMs) >= MQ_WARMUP_INTERVAL_MS;

    if (loadCell.is_ready() && hx711CalibrationReady)
    {
      hx711Initialized = true;
      float weight = loadCell.get_units(5); // Average 5 readings for noise filtering
      if (isfinite(weight))
      {
        reading.weightG = weight;
        // Zero drift compensation: slight negative values (-15g to 0g) due to temperature or vibration clamped to 0.0g
        if (weight >= -15.0f && weight < 0.0f)
        {
          reading.weightG = 0.0f;
          reading.weightValid = true;
        }
        else if (weight >= 0.0f && weight <= 50000.0f)
        {
          reading.weightValid = true;
          reading.weightG = weight;
        }
        else
        {
          reading.weightValid = false;
        }
      }
    }

    reading.distanceCm = readDistanceCm(reading.distanceValid);
    return reading;
  }

  void updateFoodPresence(const SensorReading &reading)
  {
    if (!reading.distanceValid)
    {
      return;
    }

    if (foodPresence == FoodPresence::Unknown)
    {
      foodPresence = reading.distanceCm <= FOOD_PRESENT_DISTANCE_CM
                         ? FoodPresence::Present
                         : FoodPresence::Absent;
    }
    else if (foodPresence == FoodPresence::Present &&
             reading.distanceCm >=
                 FOOD_PRESENT_DISTANCE_CM + FOOD_PRESENCE_HYSTERESIS_CM)
    {
      foodPresence = FoodPresence::Absent;
    }
    else if (foodPresence == FoodPresence::Absent &&
             reading.distanceCm <=
                 FOOD_PRESENT_DISTANCE_CM - FOOD_PRESENCE_HYSTERESIS_CM)
    {
      foodPresence = FoodPresence::Present;
    }
  }

  void updateDisplay(const SensorReading &reading)
  {
    if (!oledInitialized)
    {
      return;
    }

    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("FreshBox AI - DRAFT");
    display.printf("Wi-Fi: %s\n", WiFi.status() == WL_CONNECTED ? "online" : "offline");
    display.printf("Temp: %s", reading.temperatureValid ? "" : "--");
    if (reading.temperatureValid)
    {
      display.printf("%.1f C", reading.temperatureC);
    }
    display.println();
    display.printf("RH:   %s", reading.humidityValid ? "" : "--");
    if (reading.humidityValid)
    {
      display.printf("%.1f %%", reading.humidityPct);
    }
    display.println();
    display.printf("MQ raw: %s", reading.gasRaw >= 0 ? "" : "--");
    if (reading.gasRaw >= 0)
    {
      display.printf("%d%s", reading.gasRaw, reading.gasRawValid ? "" : " warmup");
    }
    display.println();
    if (reading.weightValid)
    {
      display.printf("Weight: %.1f g", reading.weightG);
    }
    else if (isfinite(reading.weightG) && reading.weightG < -15.0f)
    {
      display.printf("Weight: %.0f g (tare)", reading.weightG);
    }
    else
    {
      display.print("Weight: uncalibrated");
    }
    display.println();
#if FRESHBOX_HCSR04_ENABLED
    display.printf(
        "Food: %s",
        !reading.distanceValid || foodPresence == FoodPresence::Unknown
            ? "UNKNOWN"
        : foodPresence == FoodPresence::Present ? "PRESENT"
                                                : "ABSENT");
    display.println();
    display.printf("Distance: %s", reading.distanceValid ? "" : "--");
    if (reading.distanceValid)
    {
      display.printf("%.1f cm", reading.distanceCm);
    }
    display.println();
#endif
    display.display();
  }

  bool sendReading(const SensorReading &reading)
  {
    if (WiFi.status() != WL_CONNECTED)
    {
      Serial.println("Reading not uploaded: Wi-Fi is offline.");
      return false;
    }
    if (strlen(FRESHBOX_BATCH_ID) == 0)
    {
      Serial.println("Reading not uploaded: configure FRESHBOX_BATCH_ID.");
      return false;
    }

    char timestamp[32];
    if (!getTimestamp(timestamp, sizeof(timestamp)))
    {
      Serial.println("Reading not uploaded: UTC clock is not synchronized.");
      return false;
    }

    StaticJsonDocument<768> payload;
    payload["batch_id"] = FRESHBOX_BATCH_ID;
    payload["timestamp"] = timestamp;
    if (reading.temperatureValid)
    {
      payload["temperature_c"] = reading.temperatureC;
    }
    else
    {
      payload["temperature_c"] = nullptr;
    }
    if (reading.humidityValid)
    {
      payload["humidity_pct"] = reading.humidityPct;
    }
    else
    {
      payload["humidity_pct"] = nullptr;
    }
    if (reading.gasRaw >= 0)
    {
      payload["gas_raw"] = reading.gasRaw;
    }
    else
    {
      payload["gas_raw"] = nullptr;
    }
    payload["gas_calibrated"] = nullptr;
    payload["gas_calibrated_unit"] = nullptr;
    if (reading.weightValid)
    {
      payload["weight_g"] = reading.weightG;
    }
    else
    {
      payload["weight_g"] = nullptr;
    }
    payload["device_status"] = "online";
    payload["device_id"] = FRESHBOX_DEVICE_ID;
    payload["data_source"] = "physical_hardware";
    payload["idempotency_key"] = String(FRESHBOX_DEVICE_ID) + "-" + timestamp;

    JsonObject validity = payload.createNestedObject("sensor_validity");
    validity["temperature"] = reading.temperatureValid;
    validity["humidity"] = reading.humidityValid;
    validity["gas_raw"] = reading.gasRawValid;
    validity["weight"] = reading.weightValid;

    JsonObject calibration = payload.createNestedObject("calibration");
    calibration["hx711_factor_configured"] = hx711CalibrationReady;
    calibration["mq135_units"] = "raw_adc";

    String requestBody;
    serializeJson(payload, requestBody);

    String endpoint = FRESHBOX_API_BASE_URL;
    while (endpoint.endsWith("/"))
    {
      endpoint.remove(endpoint.length() - 1);
    }
    endpoint += "/api/sensors/readings";

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(endpoint))
    {
      Serial.println("Reading not uploaded: could not initialize HTTP client.");
      return false;
    }

    http.addHeader("Content-Type", "application/json");
    const int responseCode = http.POST(requestBody);
    const String responseBody = http.getString();
    http.end();

    if (responseCode < 200 || responseCode >= 300)
    {
      Serial.printf(
          "Reading upload failed: HTTP %d: %s\n",
          responseCode,
          responseBody.c_str());
      return false;
    }

    Serial.printf("Reading stored. HTTP %d: %s\n", responseCode, responseBody.c_str());
    return true;
  }

  void initializeSensors()
  {
    dht.begin();
    dhtInitialized = true;

    loadCell.begin(HX711_DOUT_PIN, HX711_SCK_PIN);
    hx711Initialized = loadCell.wait_ready_timeout(1000);
    if (hx711Initialized)
    {
      long savedOffset = 0;
      if (calibrationStorageReady)
      {
        savedOffset = calibrationStorage.getLong("offset", 0);
      }
      if (savedOffset != 0)
      {
        loadCell.set_offset(savedOffset);
        Serial.printf("HX711 restored tare offset from flash: %ld\n", savedOffset);
      }
      else
      {
        loadCell.tare(20);
        Serial.printf(
            "HX711 tared; empty-platform offset=%ld\n",
            static_cast<long>(loadCell.get_offset()));
      }

      if (hx711CalibrationReady)
      {
        float savedScale = calibrationStorageReady
                               ? calibrationStorage.getFloat(
                                     "scale", FRESHBOX_HX711_CALIBRATION_FACTOR)
                               : FRESHBOX_HX711_CALIBRATION_FACTOR;
        loadCell.set_scale(savedScale);
        Serial.printf("HX711 restored scale factor from flash: %.4f counts/g\n", savedScale);
      }
    }

    Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
    oledInitialized = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);

#if FRESHBOX_HCSR04_ENABLED
    pinMode(HCSR04_TRIG_PIN, OUTPUT);
    pinMode(HCSR04_ECHO_PIN, INPUT);
    digitalWrite(HCSR04_TRIG_PIN, LOW);
#endif

    analogReadResolution(12);
    analogSetPinAttenuation(MQ135_PIN, ADC_11db);
  }

  bool liveStreamActive = false;
  uint32_t lastLiveStreamMs = 0;

  void calibrateLoadCell(float targetMassG = HX711_CALIBRATION_MASS_G)
  {
    if (!hx711Initialized || !loadCell.is_ready())
    {
      Serial.println("Calibration failed: HX711 is not ready. Check connections.");
      return;
    }
    if (targetMassG <= 0.0f)
    {
      targetMassG = HX711_CALIBRATION_MASS_G;
    }

    Serial.printf("Calibrating with %.1f g reference... keep platform completely still.\n", targetMassG);
    delay(1000); // Allow physical vibration to settle

    const float rawChange = static_cast<float>(loadCell.get_value(30));
    if (!isfinite(rawChange) || fabsf(rawChange) < 10.0f)
    {
      Serial.printf(
          "Calibration failed: weight change too small (delta=%.0f counts). Make sure reference weight is placed.\n",
          rawChange);
      return;
    }

    const float factor = rawChange / targetMassG;
    if (!isfinite(factor) || fabsf(factor) < 0.001f)
    {
      Serial.println("Calibration failed: calculated scale factor is invalid.");
      return;
    }

    loadCell.set_scale(factor);
    hx711CalibrationReady = true;
    if (calibrationStorageReady)
    {
      calibrationStorage.putFloat("scale", factor);
    }
    Serial.printf(
        "Calibration complete! Delta=%.0f counts for %.1f g -> Factor=%.4f counts/g (saved to flash).\n",
        rawChange,
        targetMassG,
        factor);
    Serial.println("Remove the reference weight. Scale is ready! Type 'r' in Serial to see real-time weight updates.");
    emptyTareConfirmed = false;
  }

  void tareEmptyBox()
  {
    if (!hx711Initialized || !loadCell.is_ready())
    {
      Serial.println("Tare failed: HX711 is not ready. Check connections.");
      return;
    }

    Serial.println("Taring... keep the empty box and platform completely still.");
    delay(1000); // Allow settling
    loadCell.tare(30);
    emptyTareConfirmed = true;
    long offset = loadCell.get_offset();
    if (calibrationStorageReady)
    {
      calibrationStorage.putLong("offset", offset);
    }
    Serial.printf(
        "Empty-box tare complete! Offset=%ld (saved to flash).\n",
        offset);
    Serial.printf(
        "Next: place %.0f g reference weight on the box, wait 2 seconds, then send 'c'.\n",
        HX711_CALIBRATION_MASS_G);
  }

  void processCalibrationCommand()
  {
    while (Serial.available() > 0)
    {
      char c = Serial.peek();
      if (c == ' ' || c == '\r' || c == '\n')
      {
        Serial.read();
        continue;
      }

      String line = Serial.readStringUntil('\n');
      line.trim();
      if (line.length() == 0)
      {
        continue;
      }

      char cmd = line.charAt(0);
      if (cmd == 't' || cmd == 'T')
      {
        tareEmptyBox();
      }
      else if (cmd == 'c' || cmd == 'C')
      {
        float customMass = HX711_CALIBRATION_MASS_G;
        if (line.length() > 1)
        {
          float parsed = line.substring(1).toFloat();
          if (parsed > 0.0f)
          {
            customMass = parsed;
          }
        }
        calibrateLoadCell(customMass);
      }
      else if (cmd == 'r' || cmd == 'R')
      {
        liveStreamActive = !liveStreamActive;
        Serial.printf("[Stream] Live weight stream %s.\n", liveStreamActive ? "ENABLED (updates every 500ms)" : "DISABLED");
      }
      else if (cmd == '?')
      {
        Serial.println("--- FreshBox Load Cell Commands ---");
        Serial.println("  't'       : Tare empty platform (saves zero baseline to flash)");
        Serial.printf("  'c'       : Calibrate with %.0f g reference weight (saves factor to flash)\n", HX711_CALIBRATION_MASS_G);
        Serial.println("  'c <mass>': Calibrate with custom weight in grams (e.g. 'c 200' or 'c 500')");
        Serial.println("  'r'       : Toggle real-time live weight streaming (every 500ms)");
        Serial.println("  '?'       : Show this help menu");
        if (loadCell.is_ready())
        {
          long raw = loadCell.read();
          long off = loadCell.get_offset();
          float sc = loadCell.get_scale();
          float wt = (isfinite(sc) && fabsf(sc) > 0.001f) ? (float)(raw - off) / sc : 0.0f;
          Serial.printf("Current Status: Raw=%ld, Offset=%ld, Delta=%ld, Factor=%.4f, Weight=%.1f g\n",
                        raw, off, raw - off, sc, wt);
        }
        Serial.println("------------------------------------");
      }
    }
  }

} // namespace

void setup()
{
  Serial.begin(115200);
  Serial.setTimeout(100);
  delay(100);
  bootTimeMs = millis();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  calibrationStorageReady = calibrationStorage.begin("freshbox", false);
  if (!calibrationStorageReady)
  {
    Serial.println("HX711 calibration storage unavailable; calibration won't persist after restart.");
  }
  float calibrationFactor = FRESHBOX_HX711_CALIBRATION_FACTOR;
  if (calibrationStorageReady)
  {
    calibrationFactor = calibrationStorage.getFloat("scale", calibrationFactor);
  }
  hx711CalibrationReady =
      isfinite(calibrationFactor) && fabsf(calibrationFactor) >= 0.001f;
  initializeSensors();
  if (hx711Initialized)
  {
    Serial.println();
    Serial.println("--- Scale Setup & Calibration Commands ---");
    Serial.println("  't'       : Tare empty platform");
    Serial.printf("  'c'       : Calibrate with %.0f g reference weight\n", HX711_CALIBRATION_MASS_G);
    Serial.println("  'r'       : Toggle real-time live weight streaming (500ms)");
    Serial.println("  '?'       : Show help and raw ADC debug status");
    Serial.println("------------------------------------------");
  }
  connectWifi();

  Serial.println();
  Serial.println("FreshBox ESP32 firmware draft started.");
  Serial.printf("DHT22 initialized: %s\n", dhtInitialized ? "yes" : "no");
  Serial.printf("HX711 ready at startup: %s\n", hx711Initialized ? "yes" : "no");
  Serial.printf("OLED initialized: %s\n", oledInitialized ? "yes" : "no");
  Serial.println("MQ-135 reports raw ADC only; it is not calibrated ppm.");
}

void loop()
{
  processCalibrationCommand();

  const uint32_t now = millis();
  if (liveStreamActive && (now - lastLiveStreamMs >= 500))
  {
    lastLiveStreamMs = now;
    if (loadCell.is_ready())
    {
      long raw = loadCell.read();
      long offset = loadCell.get_offset();
      float scale = loadCell.get_scale();
      float grams = (isfinite(scale) && fabsf(scale) > 0.001f)
                        ? static_cast<float>(raw - offset) / scale
                        : 0.0f;
      Serial.printf("[Live Scale] Raw: %ld | Offset: %ld | Delta: %ld | Weight: %.1f g\n",
                    raw, offset, raw - offset, grams);
    }
  }

  const bool wifiConnected = WiFi.status() == WL_CONNECTED;
  if (!wifiConnected)
  {
    connectWifi();
  }
  else
  {
    if (!previousWifiConnected)
    {
      Serial.printf("Wi-Fi connected; IP: %s\n", WiFi.localIP().toString().c_str());
    }
    initializeTime();
  }
  previousWifiConnected = wifiConnected;

  if (now - lastReadingMs >= READING_INTERVAL_MS)
  {
    lastReadingMs = now;
    const SensorReading reading = readSensors();
    updateFoodPresence(reading);

    Serial.printf(
        "Reading: temp=%s humidity=%s mq_raw=%d gas_valid=%s weight=%s\n",
        reading.temperatureValid ? String(reading.temperatureC, 1).c_str() : "invalid",
        reading.humidityValid ? String(reading.humidityPct, 1).c_str() : "invalid",
        reading.gasRaw,
        reading.gasRawValid ? "yes" : "no",
        reading.weightValid
            ? String(reading.weightG, 1).c_str()
            : (isfinite(reading.weightG)
                   ? (String(reading.weightG, 1) + " (negative - send 't' to tare)").c_str()
                   : "invalid"));

    updateDisplay(reading);
    sendReading(reading);
  }

  delay(10);
}
