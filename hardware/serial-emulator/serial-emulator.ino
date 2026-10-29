// PO-x00 serial emulator for an Arduino Uno: answers fiedle400's serial backend (T-101) the way
// the mock tests' FakeOximeter does, so the serial path can be tried on a real USB-serial port.
// See README.md in this folder for flashing and running fiedle400 against it.
//
// Jumpers to GND (read before every burst of commands, so they can be changed while it runs):
//   D2 silent   D3 bad checksum   D4 split reports   D5 unpadded reports
//   D6 PO-300 (also DEFAULT_MODEL, i.e. neither jumper)   D7 PO-250
// The LED (D13) toggles on every command and stays lit after a destructive one.

#include "emulator.h"

#define DEFAULT_MODEL EMU_PO300
#define DEFAULT_FAULTS 0
// Uncomment to report another model string (at most 8 characters) in the 0xF1 reply.
// #define MODEL_STRING_OVERRIDE "50F"

static const uint8_t FAULT_PINS[] = {2, 3, 4, 5};
static const uint8_t PIN_PO300 = 6, PIN_PO250 = 7;

static Emulator emu;
static bool led, erased;

void emu_write(const uint8_t *data, uint8_t n) { Serial.write(data, n); }
void emu_delay_ms(uint16_t ms) {
  Serial.flush();  // the pause has to be on the line, not in the TX buffer
  delay(ms);
}
void emu_activity(bool destructive) {
  erased |= destructive;
  led = !led;
  digitalWrite(LED_BUILTIN, (led || erased) ? HIGH : LOW);
}

static void read_jumpers() {
  uint8_t faults = DEFAULT_FAULTS;
  for (uint8_t i = 0; i < sizeof(FAULT_PINS); i++)
    if (digitalRead(FAULT_PINS[i]) == LOW) faults |= 1 << i;
  emu.faults = faults;
  emu.model = digitalRead(PIN_PO250) == LOW ? EMU_PO250
            : digitalRead(PIN_PO300) == LOW ? EMU_PO300
            : DEFAULT_MODEL;
}

void setup() {
  for (uint8_t i = 0; i < sizeof(FAULT_PINS); i++) pinMode(FAULT_PINS[i], INPUT_PULLUP);
  pinMode(PIN_PO300, INPUT_PULLUP);
  pinMode(PIN_PO250, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
#ifdef MODEL_STRING_OVERRIDE
  emu.model_override = MODEL_STRING_OVERRIDE;
#endif
  Serial.begin(115200);  // 8N1, as SpO2.exe opens the port (PROTOCOL.md §5)
  read_jumpers();
}

void loop() {
  bool idle = true;
  while (Serial.available()) {
    if (idle) read_jumpers();
    idle = false;
    emu.feed(Serial.read(), millis());
  }
  emu.poll(millis());
}
