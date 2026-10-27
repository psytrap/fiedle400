# T-083: Arduino + servo mechanical test fixture for the PO-400 sensor

- **Status:** Done
- **Priority:** Low
- **Owner:** Local
- **Scope & Relevant Files:**
  - `hardware/wiggler/wiggler.ino`

---

## Description & Context

The ad-hoc "finger dummy" used to chase [T-082](T-082-wizard-erase-reports-success-but-sessions-persist.md)
(a phone vibrating against the sensor, driven by a free online
heartbeat-pattern vibrator) works for triggering a stored session, but
it's manual, unpowered-off-device, and not repeatable on a timer.

Build a small Arduino + servo rig instead: a servo periodically
squeezing/releasing a soft translucent pad (silicone finger cot,
eraser, etc.) clipped into the PO-400 sensor, so a test session can be
produced unattended and on a repeatable cycle (e.g. "squeeze every
800ms for 2 minutes, then stop") instead of holding a vibrating phone
against it by hand.

This is still the mechanical-pulsing approach (see the online research
done for T-082/this area), not the more precise LED-injection
technique -- good enough for generating throwaway sessions for
software testing (erase/download bugs etc.), not for controllable
SpO2/HR values. That upgrade, if ever wanted, would be a separate,
bigger ticket.

## Criteria

- [x] Arduino + servo + soft pad rig built, clips into the PO-400
      sensor the same way a finger would
- [x] Reliably produces a stored session on the device when run for a
      short cycle
- [x] Documented here (parts used, servo timing) so it can be rebuilt
      or reused for future test fixtures

## Execution Notes

**2026-10-22 (Claude, with psytrap driving the hardware):**

- Arduino Uno confirmed on `/dev/ttyACM1` (an ESP32 dev board also on this
  machine shows up as `/dev/ttyACM0` -- identified both via `udevadm`
  `ID_VENDOR`/`ID_MODEL` before touching either, so as not to flash the
  wrong board). Servo signal on pin 2.
- `arduino-cli` wasn't installed; downloaded it fresh into the scratchpad
  (not the repo), plus the `arduino:avr` core and the `Servo` library.
- Iterated the sketch live against the real rig: started as a smooth
  70-110 deg sweep, then a hard 0-180 deg snap (servo was stuck/too
  gentle), then added a slow eased return after the snap once power
  became the limiting factor (a fast return draws as much current as the
  snap itself; easing it down is much gentler), then dropped the range to
  81-99 deg (10% of full) and set the rate to 40 BPM.
- **Power gotcha hit live:** the servo was originally wired to the
  Arduino's own 5V pin, which (when only USB-powered) sags under the
  servo's movement current and can brown out/reset the board. Rewired to
  VIN -- but VIN only carries anything when a separate external supply
  (wall adapter/battery into the barrel jack) is actually connected;
  without one, VIN is just unpowered. psytrap confirmed power is still
  tight even after this; the eased-return + smaller-range changes above
  are what's actually easing the current draw, not the pin by itself.
- Settled on bang-bang motion (two direct `Servo.write()` calls, no
  interpolated steps -- psytrap preferred this over the eased return)
  at **25% of the full range (68-113 deg), 40 BPM** -- tried 10% first,
  then 25%, psytrap confirmed 25% is better.
- Not yet confirmed: whether this motion reliably registers as a pulse
  on the real PO-400 -- the device was unplugged (not found over USB)
  partway through this session and hasn't been reconnected yet.
  Criteria below still open until that's checked.

**2026-10-22, later same day (Claude, with psytrap):** psytrap suspected
the first Arduino had been killed by the servo's back-EMF/current draw
(a USB-brownout-adjacent worry, not literally EMF damage -- likely the
servo's current rating is just too high for what the board/USB port can
source). Two changes made:

- **Sketch:** added real dwell time at the top of each squeeze before
  snapping back down -- `HIGH_MS` raised from 100ms to 600ms (was
  previously just enough to register the hold, not an actual rest
  between the forward and return move). `LOW_MS` is still derived from
  the 40 BPM period minus `HIGH_MS`, so overall rate is unchanged. The
  intent: give the forward and return moves (the two direct
  `Servo.write()` bang-bang calls) more separation so they aren't a
  near-instant reversal.
- **Hardware:** a second Arduino Uno clone (CH340-based, shows up as
  `/dev/ttyUSB0`, distinct vendor/model from both the genuine Uno on
  `/dev/ttyACM1` and the ESP32 on `/dev/ttyACM0` -- checked via
  `udevadm` before flashing either) was flashed with the updated sketch
  as a spare/backup. The original Uno was then reconnected and
  reflashed too, and it came back up fine -- it was not actually dead,
  so the power-sag theory (servo current rating vs. what the board can
  source) stays the leading explanation for whatever happened, over a
  destroyed board.
- Flashing the CH340 clone hit the same transient first-command USB
  hiccup noted in T-078 (`cannot open port: Input/output error`, then a
  bootloader sync mismatch) -- resolved by retrying the upload, no
  replug needed after the first one.
- **Servo choice matters:** the servo in use is a **Tower Pro MG996R**,
  a full-size high-torque metal-gear servo -- its stall/movement current
  is well beyond what this rig needs (a soft pad squeeze) and is the
  likely root cause of the power-sag/brownout symptoms above, separate
  from the timing changes. For this fixture, use a small/micro servo
  (e.g. SG90-class) instead -- it's a lighter load that an
  Arduino+USB-only setup can actually drive, rather than relying on
  gentler timing to work around an oversized motor.
  An **SG90 has been ordered** as the replacement. Spec comparison
  (current draw is the relevant number here):

  | | SG90 | MG996R |
  |---|---|---|
  | Stall current | ~360-650mA | ~2.5A |
  | Running current | ~100-250mA | ~500mA |
  | Stall torque | 1.8 kg-cm | 9.4-11 kg-cm |
  | Weight / gears | 9g, plastic | 55g, metal |

  MG996R stall current (2.5A) is 5-7x the SG90's, and far above what
  an Arduino 5V pin (~500mA total) or a USB port can source -- matches
  the brownout symptoms well. The SG90's own worst case (~650mA stall)
  is still above the 5V pin's safe limit, so VIN + an external supply
  is still the proper fix if/when available, but the SG90 is a much
  more forgiving load for a USB-only setup in the meantime.

**2026-10-27 (psytrap):** Confirmed working end-to-end -- the rig, now
running the **SG90** (the replacement ordered after the MG996R
brownout/current issues above), reliably registered as a pulse and
produced a stored session on the real PO-400. Closes the one remaining
open item from the notes above (whether the bang-bang motion would
actually register, last left unconfirmed when the device was unplugged
mid-session). All three criteria met; closing the ticket.

## Physical Setup

- **Arduino Uno**, servo signal wire on pin **2**.
- **Servo power**: as wired for the MG996R, this was the Arduino's own
  **5V** pin (not VIN), which sagged under that servo's movement current
  on USB power alone (see above). Now running the SG90 instead (2026-10-27,
  confirmed working) -- its lighter current draw is exactly why it
  replaced the MG996R, but the exact wiring used for this run (still 5V,
  or moved to VIN) wasn't recorded here; check before relying on this
  description if rebuilding the rig.
- **Linkage into the sensor**: a stiff wire ("Draht") from the servo
  arm, bent to reach into the PO-400's finger clip.
- **Filler**: the clip is sized for a finger, not a bare wire, so a
  pill capsule is wedged in as a filler/spacer to fill out the clip and
  give the wire's motion something to actually press against inside
  it.
- **Motion**: bang-bang between 68-113 deg (25% of the servo's full
  180 deg range) at 40 BPM -- see `hardware/wiggler/wiggler.ino`.
- **Positioning check**: the sensor's own LED needs to stay red (not
  flicker to another indicator state) for the wire/capsule placement
  inside the clip to count as good contact -- reposition the capsule
  if it doesn't.
- **Mounting**: the whole rig (Arduino, servo, sensor clip) is taped
  down to the table to keep everything in a fixed position relative to
  each other, so the wire stays seated in the clip between runs.
