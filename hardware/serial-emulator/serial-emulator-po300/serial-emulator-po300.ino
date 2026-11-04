// PO-300 variant of the PO-x00 serial emulator. See ../README.md for flashing and running
// fiedle400 against it. The PO-250, PO-400 and CMS50F 3.7 models are sibling sketches
// (../serial-emulator-po250/, -po400/, -cms50f/) -- flash the one matching the model you want;
// there is no default (psytrap, 2026-11-04).
//
// Fault jumpers to GND, same as every sibling sketch:
//   D2 silent   D3 bad checksum   D4 split reports   D5 unpadded reports
// The LED (D13) toggles on every command and stays lit after a destructive one.

#include "emulator.h"

#define DEFAULT_MODEL EMU_PO300
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
