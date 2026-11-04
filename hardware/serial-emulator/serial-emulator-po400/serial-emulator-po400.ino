// PO-400-over-serial variant of the PO-x00 serial emulator. See ../README.md for flashing and
// running fiedle400 against it, and ../serial-emulator.ino (the PO-250 default) for the shared
// design notes. This sketch differs only in DEFAULT_MODEL -- flash this one instead of the
// PO-250 sketch to get PO-400 (protocol C, as actually captured) replies over a serial port;
// no jumper needed (psytrap, 2026-11-04).
//
// Fault jumpers to GND, same as every derivative sketch:
//   D2 silent   D3 bad checksum   D4 split reports   D5 unpadded reports
// The LED (D13) toggles on every command and stays lit after a destructive one.

#include "emulator.h"

#define DEFAULT_MODEL EMU_PO400
#define DEFAULT_FAULTS 0
// Uncomment to report another model string (at most 8 characters in the 0xF1 reply).
// #define MODEL_STRING_OVERRIDE "50F"

static const uint8_t FAULT_PINS[] = {2, 3, 4, 5};

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

static void read_fault_jumpers() {
  uint8_t faults = DEFAULT_FAULTS;
  for (uint8_t i = 0; i < sizeof(FAULT_PINS); i++)
    if (digitalRead(FAULT_PINS[i]) == LOW) faults |= 1 << i;
  emu.faults = faults;
}

void setup() {
  for (uint8_t i = 0; i < sizeof(FAULT_PINS); i++) pinMode(FAULT_PINS[i], INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  emu.model = DEFAULT_MODEL;
#ifdef MODEL_STRING_OVERRIDE
  emu.model_override = MODEL_STRING_OVERRIDE;
#endif
  Serial.begin(115200);  // 8N1, as SpO2.exe opens the port (PROTOCOL.md §5)
  read_fault_jumpers();
}

void loop() {
  bool idle = true;
  while (Serial.available()) {
    if (idle) read_fault_jumpers();
    idle = false;
    emu.feed(Serial.read(), millis());
  }
  emu.poll(millis());
}
