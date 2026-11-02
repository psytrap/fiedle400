// Core of the PO-x00 serial emulator: plain C++, so the same code runs on the Uno
// (serial-emulator.ino) and on a PC against a pseudo-terminal (host_sim.cpp).
//
// The includer defines PROGMEM, pgm_read_byte() and these three functions:
//   void emu_write(const uint8_t *data, uint8_t n);   // bytes to the host
//   void emu_delay_ms(uint16_t ms);
//   void emu_activity(bool destructive);              // a command arrived (LED)
//
// What it answers is the PO-400's recorded replies (trace_data.h, the same traces the mock
// tests replay). For the PO-250 and PO-300 these are assumptions: SpO2 Assistant sends the
// PO-400's commands to every model (PROTOCOL.md §5), but no reply of those models was ever
// captured (T-102).
#pragma once

#include <stdint.h>
#include <string.h>

void emu_write(const uint8_t *data, uint8_t n);
void emu_delay_ms(uint16_t ms);
void emu_activity(bool destructive);

enum { TRACE_COMMON = 1, TRACE_AUTO = 2, TRACE_MANUAL = 4 };
#include "trace_data.h"

// Faults, any combination.
enum {
  FAULT_SILENT = 1,        // read everything, answer nothing (a foreign device on the port)
  FAULT_BAD_CHECKSUM = 2,  // last byte of every reply report off by one
  FAULT_SPLIT = 4,         // 20 ms pause in the middle of every report (a slow adapter)
  FAULT_UNPADDED = 8,      // send reports without their zero padding (how a real serial model may answer)
};

struct EmuModel {
  const char *name;
  const char *model_string;  // the 8 bytes of the 0xF1 reply (protocol C), or the A8 model
                              // string (protocol B); space padded either way
  uint8_t storage;           // protocol C only: which TRACE_* keys this model answers
  bool protocol_b;           // speaks protocol B (CMS50F family, PROTOCOL_B.md) instead of C
};

// PO-250 and PO-300 model strings are unknown (PROTOCOL.md §6.3); these are placeholders, so
// fiedle400 shows them as "Unknown PO-x00 family device".
//
// EMU_PO300_PROTOCOL_B: a real PO-300 owner's unit answered "Smart Device Assistant" but not
// "SpO2 Assistant" (CMS50_COMPATIBILITY.md finding 6), and a disassembly of the former's bundled
// SpO2.exe found it sends protocol B's command set (PROTOCOL_B.md §5.2) -- unconfirmed on a real
// PO-300, but worth emulating so fiedle400's probe-and-refuse path (T-105, detection only) can be
// tried against something other than a Python mock. Detection only: there is no protocol-B
// download reply here, matching fiedle400 itself.
static const EmuModel EMU_MODELS[] = {
  {"PO-400", "50F", TRACE_COMMON | TRACE_AUTO | TRACE_MANUAL, false},  // as captured
  {"PO-300", "EMU-300", TRACE_COMMON | TRACE_AUTO | TRACE_MANUAL, false},  // Auto+Manual like the PO-400
  {"PO-250", "EMU-250", TRACE_COMMON | TRACE_MANUAL, false},  // one Manual recording, no Auto list
  {"PO-300 (protocol B guess)", "CMS50F", 0, true},
};
enum { EMU_PO400 = 0, EMU_PO300 = 1, EMU_PO250 = 2, EMU_PO300_PROTOCOL_B = 3 };

static const uint8_t EMU_REPORT = 64;
static const uint8_t EMU_GAP_MS = 3;  // a quiet line this long ends a burst of commands

class Emulator {
 public:
  uint8_t model = EMU_PO400;
  const char *model_override = nullptr;  // replaces the model's string when set
  uint8_t faults = 0;
  uint16_t commands = 0, unanswered = 0, destructive = 0;

  void feed(uint8_t b, uint32_t now_ms) {
    if (len_ == sizeof(buf_)) process();
    buf_[len_++] = b;
    last_ms_ = now_ms;
  }

  void poll(uint32_t now_ms) {
    if (len_ && (uint32_t)(now_ms - last_ms_) >= EMU_GAP_MS) process();
  }

 private:
  uint8_t buf_[128];
  uint8_t len_ = 0;
  uint32_t last_ms_ = 0;
  uint8_t out_[EMU_REPORT];

  void process() {
    if (EMU_MODELS[model].protocol_b) { process_b(); return; }
    process_c();
  }

  // Protocol B (PROTOCOL_B.md §1): every request is exactly 9 bytes, `7D 81 [op] ... `, no
  // checksum -- no need for protocol C's bare/checksum-delimited scanning below. A byte that
  // is not `7D 81` at a frame boundary is skipped one at a time (foreign noise); an incomplete
  // trailing frame (a burst cut mid-write) is dropped, same as protocol C's handling of leftovers.
  void process_b() {
    uint8_t p = 0, n = len_;
    while (p + 9 <= n) {
      if (buf_[p] == 0x7D && buf_[p + 1] == 0x81) {
        handle_b(buf_ + p);
        p += 9;
      } else {
        p++;
      }
    }
    len_ = 0;
  }

  // Commands arrive without report boundaries (serial_port.unpad_report), so a burst is cut
  // into commands by their shape: 7D 81 frames run to the next 7D, bare commands end with
  // their checksum (PROTOCOL.md §1.2).
  void process_c() {
    uint8_t p = 0, n = len_;
    while (p < n) {
      const uint8_t *b = buf_ + p;
      uint8_t left = n - p;
      if (left >= 3 && b[0] == 0x7D && b[1] == 0x81) {
        if (b[2] == 0xA7 && (left == 3 || b[3] == 0x80)) {
          // The unlock: 7D 81 A7 80x6 7D 81 A2. No reply.
          uint8_t q = 3;
          while (q < left && b[q] == 0x80) q++;
          if (q + 3 <= left && b[q] == 0x7D && b[q + 1] == 0x81 && b[q + 2] == 0xA2) q += 3;
          commands++;
          emu_activity(false);
          p += q;
          continue;
        }
        uint8_t q = 3;
        while (q < left && b[q] != 0x7D) q++;
        handle(b + 2, q - 2);
        p += q;
        continue;
      }
      if (b[0] < 0x80) {  // not a command start: line noise, or a modem probe's "AT"
        p++;
        continue;
      }
      handle(b, bare_length(b, left));
      p += bare_length(b, left);
    }
    len_ = 0;
  }

  static uint8_t bare_length(const uint8_t *b, uint8_t left) {
    uint8_t fixed = b[0] == 0x82 ? 8 : b[0] == 0x83 ? 10 : 0;  // clock commands: other checksums
    if (fixed) return fixed < left ? fixed : left;
    uint8_t sum = b[0];
    for (uint8_t i = 1; i < left; i++) {
      if (b[i] == (sum & 0x7F)) return i + 1;
      sum += b[i];
    }
    return left;
  }

  static bool is_destructive(const uint8_t *c, uint8_t n) {
    switch (c[0]) {
      case 0x91: case 0x92: case 0x93: case 0x95: case 0x96:
      case 0xA1: case 0xAA: case 0xAB: case 0xAC:
        return true;
      case 0x94: return n > 1 && c[1] != 0x14;
      case 0x9D: return n > 1 && c[1] == 0x7F;  // 9D 7F: erase (PROTOCOL.md 3.13)
    }
    return false;
  }

  // One command, without its 7D 81 prefix.
  void handle(const uint8_t *c, uint8_t n) {
    commands++;
    if (is_destructive(c, n)) {
      destructive++;  // never erases anything, never answers
      emu_activity(true);
      return;
    }
    emu_activity(false);
    if (c[0] == 0x81) {
      send_model();
      return;
    }
    // Longest recorded key that this command starts with, among the model's storage kinds.
    const uint8_t *best = nullptr;
    uint8_t best_len = 0;
    const uint8_t *e = TRACE_TABLE;
    uint8_t storage = EMU_MODELS[model].storage;
    while (uint8_t flags = pgm_read_byte(e)) {
      uint8_t klen = pgm_read_byte(e + 1);
      const uint8_t *key = e + 2;
      const uint8_t *r = key + klen;
      if ((flags & storage) && klen <= n && klen > best_len) {
        uint8_t i = 0;
        while (i < klen && pgm_read_byte(key + i) == c[i]) i++;
        if (i == klen) {
          best = r;
          best_len = klen;
        }
      }
      uint8_t reports = pgm_read_byte(r++);
      while (reports--) r += 1 + pgm_read_byte(r);
      e = r;
    }
    if (!best) {
      unanswered++;
      return;
    }
    uint8_t reports = pgm_read_byte(best++);
    while (reports--) {
      uint8_t rlen = pgm_read_byte(best++);
      for (uint8_t i = 0; i < rlen; i++) out_[i] = pgm_read_byte(best + i);
      best += rlen;
      send_report(rlen);
    }
  }

  // Protocol B (PROTOCOL_B.md §2.1): `f` is one complete 9-byte frame, `f[0..1]` already
  // checked as `7D 81`. Enough to answer fiedle400's detection-only probe (hello + model
  // query); every other opcode, including `AE` (erase), gets no reply at all -- there is no
  // download engine on either side of this (T-105 is on hold).
  void handle_b(const uint8_t *f) {
    commands++;
    uint8_t op = f[2];
    if (op == 0xAE) {  // erase: never answered, never performed
      destructive++;
      emu_activity(true);
      return;
    }
    emu_activity(false);
    if (op == 0xA7 || op == 0xA2) {  // hello (stop stored / stop live stream) -> ack
      out_[0] = 0x0C;
      out_[1] = 0x00;
      send_report_b(2);
      return;
    }
    if (op == 0xA8) {  // model query -> one 0x02 frame (no continuation frame needed: <= 6 chars)
      const char *s = model_override ? model_override : EMU_MODELS[model].model_string;
      out_[0] = 0x02;
      out_[1] = 0x00;  // every byte below is plain ASCII, so no bit 7 to restore
      out_[2] = 0x00;  // marker: this is the first (and only) model frame
      for (uint8_t i = 0; i < 6; i++) out_[3 + i] = *s ? (uint8_t)*s++ : ' ';
      send_report_b(9);
      return;
    }
    unanswered++;  // A9/A3/A4/A5/A6/...: not emulated, matching fiedle400's own non-support
  }

  // out_[0..len) holds a protocol-B reply without padding. No checksum fault to apply: protocol
  // B has none (PROTOCOL_B.md §1.2).
  void send_report_b(uint8_t len) {
    if (faults & FAULT_SILENT) return;
    uint8_t total = len;
    if (!(faults & FAULT_UNPADDED)) {
      memset(out_ + len, 0, EMU_REPORT - len);
      total = EMU_REPORT;
    }
    if (faults & FAULT_SPLIT) {
      uint8_t half = total / 2;
      emu_write(out_, half);
      emu_delay_ms(20);
      emu_write(out_ + half, total - half);
    } else {
      emu_write(out_, total);
    }
  }

  void send_model() {
    const char *s = model_override ? model_override : EMU_MODELS[model].model_string;
    out_[0] = 0xF1;
    uint8_t sum = 0xF1;
    for (uint8_t i = 0; i < 8; i++) {
      uint8_t ch = *s ? (uint8_t)*s++ : ' ';
      out_[1 + i] = ch;
      sum += ch;
    }
    out_[9] = sum & 0x7F;
    send_report(10);
  }

  // out_[0..len) holds the report without padding.
  void send_report(uint8_t len) {
    if (faults & FAULT_SILENT) return;
    if (faults & FAULT_BAD_CHECKSUM) {
      uint8_t &last = out_[len - 1];
      last = (last & 0x80) | ((last + 1) & 0x7F);
    }
    uint8_t total = len;
    if (!(faults & FAULT_UNPADDED)) {
      memset(out_ + len, 0, EMU_REPORT - len);
      total = EMU_REPORT;
    }
    if (faults & FAULT_SPLIT) {
      uint8_t half = total / 2;
      emu_write(out_, half);
      emu_delay_ms(20);
      emu_write(out_ + half, total - half);
    } else {
      emu_write(out_, total);
    }
  }
};
