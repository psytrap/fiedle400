#include <Servo.h>

// Quick-and-dirty finger-dummy wiggler (T-083): a servo on pin 2 pulses a soft
// pad clipped into the PO-400 sensor, to produce throwaway test recordings
// without needing a real finger. Bang-bang motion -- two direct writes, no
// intermediate interpolation steps -- the servo itself is left to slew at
// whatever speed it can between the two positions.
Servo wiggler;

const int PIN = 2;
const int ANGLE_LOW = 68;   // 25% of the full 180 deg range, centered at 90
const int ANGLE_HIGH = 113;

const int BPM = 40;
const long PERIOD_MS = 60000L / BPM;   // 1500ms at 40 BPM

// Rest held at ANGLE_HIGH before snapping back down to ANGLE_LOW -- i.e. the
// pause between the forward and return moves within a single wiggle, not
// between separate beats. Longer than the old 100ms so the two direct writes
// (bang-bang, no interpolation) aren't a near-instant reversal -- the first
// Arduino likely died from the back-EMF/brownout stress of that.
const long HIGH_MS = 600;
const long LOW_MS = PERIOD_MS - HIGH_MS;

void setup() {
  wiggler.attach(PIN);
  wiggler.write(ANGLE_LOW);
}

void loop() {
  wiggler.write(ANGLE_HIGH);
  delay(HIGH_MS);
  wiggler.write(ANGLE_LOW);
  delay(LOW_MS);
}
