/*
 * Enhanced Pull-up Counter with HC-SR04 + ESP32
 * Features:
 * - Better error handling
 * - LED status indicators
 * - Configurable parameters
 * - Reconnection logic
 * - Debug mode
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

/* ------ USER CONFIGURATION ------ */
const char* WIFI_SSID     = "Sinalan";
const char* WIFI_PASS     = "Mali&Mojito";

const char* SUPA_URL      = "https://xgoibwxiwfagcqjuslad.supabase.co/rest/v1/rpc/increment_reps_today";
const char* SUPA_API_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhnb2lid3hpd2ZhZ2NxanVzbGFkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc5MjgzNDAsImV4cCI6MjA2MzUwNDM0MH0.75bE3UKyB5vt6hzfbfYa1MQmXU0hhORials6bV_V2bk";

/* ------ HARDWARE PINS ------ */
const uint8_t TRIG_PIN    = 5;
const uint8_t ECHO_PIN    = 18;
const uint8_t LED_BUILTIN = 2;  // Built-in LED for status

/* ------ DETECTION PARAMETERS ------ */
const float  THRESHOLD_CM      = 5.0;   // Distance for rep detection
const float  RESET_CM          = 10.0;  // Distance to reset for next rep
const float  MAX_DISTANCE_CM   = 100.0; // Maximum valid distance
const unsigned long PING_INTERVAL_MS  = 60;   // Sensor reading interval
const unsigned long MAX_ECHO_TIME_US  = 30000; // Timeout for echo
const unsigned long DEBOUNCE_MS       = 500;   // Minimum time between reps

/* ------ DEBUG MODE ------ */
const bool DEBUG_MODE = true;  // Set to false to reduce serial output

/* ------ State Variables ------ */
bool armed = true;
bool wifiConnected = false;
unsigned long lastPing = 0;
unsigned long lastRep = 0;
int dailyReps = 0;
int failedRequests = 0;

/* ------ Function Declarations ------ */
void connectWiFi();
void blinkLED(int times, int delayMs = 100);
float readDistanceCm();
bool postRep();
void handleRep();

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Pull-up Counter Starting ===");
  
  // Configure pins
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  
  // Initial LED indication
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  
  // Connect to WiFi
  connectWiFi();
}

void loop() {
  unsigned long now = millis();
  
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    if (wifiConnected) {
      wifiConnected = false;
      Serial.println("❌ WiFi connection lost!");
    }
    connectWiFi();
    return;
  }
  
  // Read sensor at specified interval
  if (now - lastPing >= PING_INTERVAL_MS) {
    lastPing = now;
    float distance = readDistanceCm();
    
    if (DEBUG_MODE && distance > 0) {
      Serial.print("Distance: ");
      Serial.print(distance, 1);
      Serial.println(" cm");
    }
    
    // Check for valid rep
    if (armed && distance > 0 && distance <= THRESHOLD_CM) {
      // Debounce check
      if (now - lastRep >= DEBOUNCE_MS) {
        handleRep();
        lastRep = now;
      }
    } 
    // Reset when head is clear
    else if (!armed && (distance < 0 || distance >= RESET_CM)) {
      armed = true;
      if (DEBUG_MODE) {
        Serial.println("🔄 Ready for next rep");
      }
    }
  }
  
  // Blink LED periodically to show system is alive
  static unsigned long lastBlink = 0;
  if (now - lastBlink >= 5000) {
    lastBlink = now;
    blinkLED(1, 50);
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  
  Serial.print("📡 Connecting to WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n✅ WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    blinkLED(3, 200);  // Success indication
  } else {
    Serial.println("\n❌ WiFi connection failed!");
    blinkLED(5, 100);  // Error indication
    delay(5000);  // Wait before retry
  }
}

float readDistanceCm() {
  // Send trigger pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  // Read echo pulse
  long duration = pulseIn(ECHO_PIN, HIGH, MAX_ECHO_TIME_US);
  
  if (duration == 0) {
    return -1;  // Timeout/out of range
  }
  
  // Calculate distance (speed of sound = 343 m/s)
  float distance = duration / 58.0;
  
  // Validate distance
  if (distance > MAX_DISTANCE_CM) {
    return -1;  // Beyond maximum range
  }
  
  return distance;
}

void handleRep() {
  Serial.println("✅ Pull-up detected!");
  dailyReps++;
  armed = false;
  
  // Visual feedback
  digitalWrite(LED_BUILTIN, HIGH);
  
  // Send to Supabase
  if (postRep()) {
    Serial.print("📊 Daily total: ");
    Serial.print(dailyReps);
    Serial.println(" reps");
    failedRequests = 0;
    blinkLED(2, 100);  // Success blink
  } else {
    Serial.println("⚠️ Failed to log rep!");
    failedRequests++;
    
    // If too many failures, try reconnecting WiFi
    if (failedRequests >= 3) {
      Serial.println("🔄 Reconnecting WiFi...");
      WiFi.disconnect();
      delay(1000);
      connectWiFi();
      failedRequests = 0;
    }
  }
  
  digitalWrite(LED_BUILTIN, LOW);
}

bool postRep() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  
  WiFiClientSecure client;
  client.setInsecure();  // For HTTPS
  
  HTTPClient http;
  http.begin(client, SUPA_URL);
  http.setTimeout(5000);  // 5 second timeout
  
  // Set headers
  http.addHeader("apikey", SUPA_API_KEY);
  http.addHeader("Authorization", "Bearer " + String(SUPA_API_KEY));
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Prefer", "return=minimal");
  
  // Send POST request
  int httpCode = http.POST("{}");
  
  if (DEBUG_MODE) {
    Serial.print("HTTP Response: ");
    Serial.println(httpCode);
  }
  
  http.end();
  
  return (httpCode >= 200 && httpCode < 300);
}

void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_BUILTIN, LOW);
    if (i < times - 1) delay(delayMs);
  }
}
