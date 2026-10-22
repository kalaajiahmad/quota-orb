#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Heltec WiFi Kit 32 V2, classic ESP32, NOT the S3/V3 pinout.
constexpr int OLED_SDA = 4, OLED_SCL = 15, OLED_RST = 16;
constexpr int BUTTON = 0;
constexpr size_t FRAME_BYTES = 1024;
Adafruit_SSD1306 oled(128, 64, &Wire, OLED_RST);
char line[2120];
size_t lineLen = 0;
bool dropping = false, oledOk = false, online = false;
uint32_t lastByte = 0, lastFrame = 0;
int brightness = 1;
bool flipped = false;

uint32_t crc32(const uint8_t *data, size_t size) {
  uint32_t crc = 0xffffffff;
  for (size_t i = 0; i < size; ++i) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; ++bit)
      crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1)));
  }
  return ~crc;
}

void message(const char *title, const char *detail) {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 3); oled.print("QUOTA ORB");
  oled.drawFastHLine(0, 15, 128, SSD1306_WHITE);
  oled.setCursor(0, 26); oled.print(title);
  oled.setCursor(0, 43); oled.print(detail);
  oled.display();
}

void hello() {
  Serial.printf("{\"type\":\"hello\",\"protocol\":1,\"oled\":%s,\"width\":128,\"height\":64,\"firmware\":\"1.0.0\",\"uptime_ms\":%lu}\n",
                oledOk ? "true" : "false", (unsigned long)millis());
}

int unhex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

void command() {
  line[lineLen] = 0;
  if (!strcmp(line, "PING")) { hello(); return; }
  if (line[0] != 'F' || line[1] != ' ') {
    Serial.println("{\"type\":\"error\",\"reason\":\"command\"}"); return;
  }
  char *end;
  unsigned long seq = strtoul(line + 2, &end, 10);
  if (end == line + 2 || *end != ' ') return;
  char *crcStart = end + 1;
  uint32_t expected = strtoul(crcStart, &end, 16);
  if (end - crcStart != 8 || *end != ' ') return;
  const char *hex = end + 1;
  uint8_t pixels[FRAME_BYTES];
  bool valid = strlen(hex) == FRAME_BYTES * 2;
  if (valid) for (size_t i = 0; i < FRAME_BYTES; ++i) {
    int a = unhex(hex[2 * i]), b = unhex(hex[2 * i + 1]);
    if (a < 0 || b < 0) { valid = false; break; }
    pixels[i] = (a << 4) | b;
  }
  if (!valid || crc32(pixels, FRAME_BYTES) != expected || !oledOk) {
    Serial.printf("{\"type\":\"nack\",\"seq\":%lu}\n", seq); return;
  }
  memcpy(oled.getBuffer(), pixels, FRAME_BYTES);
  oled.display();
  lastFrame = millis(); online = true;
  Serial.printf("{\"type\":\"ack\",\"seq\":%lu,\"crc\":%lu}\n", seq, (unsigned long)expected);
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON, INPUT_PULLUP);
  Wire.begin(OLED_SDA, OLED_SCL);
  // begin() resets the OLED and does not itself confirm device presence.
  bool allocated = oled.begin(SSD1306_SWITCHCAPVCC, 0x3c, true, false);
  Wire.beginTransmission(0x3c);
  oledOk = allocated && Wire.endTransmission() == 0;
  if (oledOk) {
    oled.ssd1306_command(SSD1306_SETCONTRAST);
    oled.ssd1306_command(100);
    message("WAITING FOR USB", "Run Start.ps1 on PC");
  }
  hello();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    lastByte = millis();
    if (c == '\n') {
      if (!dropping && lineLen) command();
      lineLen = 0; dropping = false;
    } else if (c != '\r') {
      if (lineLen < sizeof(line) - 1 && !dropping) line[lineLen++] = c;
      else dropping = true;
    }
  }
  if ((lineLen || dropping) && millis() - lastByte > 700) {
    lineLen = 0; dropping = false;
  }
  if (online && millis() - lastFrame > 6000) {
    online = false;
    message("USB OFFLINE", "Reconnect PC bridge");
    Serial.println("{\"type\":\"offline\"}");
  }
  static bool raw = true, stable = true;
  static uint32_t changed = 0, pressed = 0;
  bool state = digitalRead(BUTTON);
  if (state != raw) { raw = state; changed = millis(); }
  if (raw != stable && millis() - changed > 40) {
    stable = raw;
    if (!stable) pressed = millis();
    else {
      uint32_t held = millis() - pressed;
      if (held > 1800) {
        flipped = !flipped;
        // Rotate the controller output; host framebuffer remains unchanged.
        oled.ssd1306_command(flipped ? SSD1306_SEGREMAP : SSD1306_SEGREMAP | 1);
        oled.ssd1306_command(flipped ? SSD1306_COMSCANINC : SSD1306_COMSCANDEC);
        Serial.println("{\"type\":\"orientation\"}");
      } else if (held > 600) {
        brightness = (brightness + 1) % 3;
        const uint8_t levels[] = {12, 100, 220};
        oled.ssd1306_command(SSD1306_SETCONTRAST);
        oled.ssd1306_command(levels[brightness]);
        Serial.println("{\"type\":\"brightness\"}");
      } else Serial.println("{\"type\":\"button\"}");
    }
  }
  delay(1);
}
