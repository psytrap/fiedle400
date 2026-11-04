// Core of the PO-x00 serial emulator: plain C++, so the same code runs on the Uno
// (serial-emulator.ino) and on a PC against a pseudo-terminal (host_sim.cpp).
//
// The includer defines PROGMEM, pgm_read_byte() and these three functions:
//   void emu_write(const uint8_t *data, uint8_t n);   // bytes to the host
//   void emu_delay_ms(uint16_t ms);
//   void emu_activity(bool destructive);              // a command arrived (LED)
//
// What it answers in protocol C (PO-400, PO-300) is the PO-400's recorded replies
// (trace_data.h, the same traces the mock tests replay). For the PO-300 these are assumptions:
// SpO2 Assistant sends the PO-400's commands to every model (PROTOCOL.md §5), but no reply of
// that model was ever captured (T-102). In protocol B (PO-250, CMS50F; T-105) it replays a real
// CMS50F 3.7 download from 2014 (tests/fixtures/cms50f37-download.trace.json); the PO-250 speaks
// that protocol (kaivol/pulox), but no PO-250 reply was ever captured either.
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
  bool protocol_b;           // speaks protocol B (PO-250, CMS50F family; PROTOCOL_B.md) instead of C
};

// PO-250 and PO-300 model strings are unknown (PROTOCOL.md §6.3, T-105); these are
// placeholders. fiedle400 shows "EMU-300" as "Unknown PO-x00 family device", and takes any
// protocol-B device that does not name itself CMS50* as a PO-250 (psytrap, 2026-11-04).
//
// EMU_CMS50F: a CMS50F with firmware 3.7, as captured; same protocol and data as the PO-250, but
// fiedle400 refuses it by its model string (T-105), so this proves the refusal end to end.
static const EmuModel EMU_MODELS[] = {
  {"PO-400", "50F", TRACE_COMMON | TRACE_AUTO | TRACE_MANUAL, false},  // as captured
  {"PO-300", "EMU-300", TRACE_COMMON | TRACE_AUTO | TRACE_MANUAL, false},  // Auto+Manual like the PO-400
  {"PO-250 (protocol B)", "EMU-250", 0, true},  // one recording, replayed from the 2014 capture
  {"CMS50F 3.7 (protocol B)", "CMS50F", 0, true},
};
enum { EMU_PO400 = 0, EMU_PO300 = 1, EMU_PO250 = 2, EMU_CMS50F = 3 };

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
  // checked as `7D 81`. Answers the hello, the model query and the read-only download commands
  // (A3, A4, A5, AD as captured; A6 from B_SAMPLES) for recording #1 of user 1. Everything else,
  // `AE` (erase) and `AA` (set/ask device id) included, gets no reply.
  void handle_b(const uint8_t *f) {
    commands++;
    uint8_t op = f[2], session = f[4] & 0x7F;
    if (op == 0xAE || op == 0xAA) {  // erase / device id: never answered, never performed
      destructive++;
      emu_activity(true);
      return;
    }
    emu_activity(false);
    if (op == 0xA7 || op == 0xA2) {  // hello (stop stored / stop live stream) -> 0C 80
      out_[0] = 0x0C;
      out_[1] = 0x80;
      send_b(2);
      return;
    }
    if (op == 0xA8) {  // model query -> two 0x02 frames of 6 characters, as the CMS50F sends
      const char *s = model_override ? model_override : EMU_MODELS[model].model_string;
      for (uint8_t part = 0; part < 2; part++) {
        out_[0] = 0x02;
        out_[1] = part ? 0x81 : 0x80;  // bit 0: data byte 0 has bit 7 set (0xFF marks the 2nd frame)
        out_[2] = part ? 0xFF : 0x80;
        for (uint8_t i = 0; i < 6; i++) out_[3 + i] = (*s ? (uint8_t)*s++ : ' ') | 0x80;
        send_b(9);
      }
      return;
    }
    if (op == 0xA6) {
      if (session == 0) send_samples_b();
      else unanswered++;
      return;
    }
    if (session != 0 && (op == 0xA4 || op == 0xA5)) {  // only recording #1 exists
      unanswered++;
      return;
    }
    const uint8_t *e = B_REPLIES;
    while (uint8_t opcode = pgm_read_byte(e)) {
      uint8_t n = pgm_read_byte(e + 1);
      if (opcode == op) {
        for (uint8_t i = 0; i < n; i++) out_[i] = pgm_read_byte(e + 2 + i);
        send_b(n);
        return;
      }
      e += 2 + n;
    }
    unanswered++;  // A9, AB, B0, ...: not emulated
  }

  // The A6 stream: 0x0F frames of three (SpO2, pulse) samples, high bits in byte 1. The device
  // then just goes quiet: the capture holds 8,202 of the 20,904 samples A4 announces, so
  // fiedle400 warns about the rest, as in its replay test.
  void send_samples_b() {
    uint8_t frame[6], k = 0;
    const uint8_t *r = B_SAMPLES;
    for (uint16_t run = 0; run < B_SAMPLE_RUNS; run++, r += 3) {
      uint8_t spo2 = pgm_read_byte(r), pulse = pgm_read_byte(r + 1), count = pgm_read_byte(r + 2);
      while (count--) {
        frame[k++] = spo2;
        frame[k++] = pulse;
        if (k == 6) {
          out_[0] = 0x0F;
          out_[1] = 0x80;
          for (uint8_t i = 0; i < 6; i++) {
            if (frame[i] & 0x80) out_[1] |= 1 << i;
            out_[2 + i] = frame[i] | 0x80;
          }
          send_b(8);
          k = 0;
        }
      }
    }
  }

  // out_[0..len) holds one protocol-B frame. Sent as is: protocol-B devices do not pad their
  // replies (the capture has none) and there is no checksum to break (PROTOCOL_B.md §1.2).
  void send_b(uint8_t len) {
    if (faults & FAULT_SILENT) return;
    if (faults & FAULT_SPLIT) {
      uint8_t half = len / 2;
      emu_write(out_, half);
      emu_delay_ms(20);
      emu_write(out_ + half, len - half);
    } else {
      emu_write(out_, len);
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
