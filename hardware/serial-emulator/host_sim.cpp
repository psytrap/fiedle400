// The emulator core on a PC: serves it on a pseudo-terminal, so fiedle400's real serial code
// (termios, SerialBackend) can be run against it without a board. Linux/macOS only.
//
//   g++ -O2 -o host_sim hardware/serial-emulator/host_sim.cpp
//   ./host_sim /tmp/ttyACM-emu [po400|po300|po250] [silent,badsum,split,unpadded] [MODEL]
//   python3 -m fiedle400 -d /tmp/ttyACM-emu info
//
// The link's name must start with "ttyACM" or "ttyUSB" for fiedle400 to treat it as a serial
// port. Serves one connection: it exits when the host closes the port.
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define PROGMEM
#define pgm_read_byte(p) (*(const uint8_t *)(p))

#include "emulator.h"

static int master_fd = -1;

void emu_write(const uint8_t *data, uint8_t n) {
  while (n) {
    ssize_t k = write(master_fd, data, n);
    if (k <= 0) return;
    data += k;
    n -= (uint8_t)k;
  }
}
void emu_delay_ms(uint16_t ms) { usleep(ms * 1000u); }
void emu_activity(bool) {}

static uint32_t now_ms() {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint32_t)(ts.tv_sec * 1000u + ts.tv_nsec / 1000000u);
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s LINK [po400|po300|po250] [faults] [MODEL]\n", argv[0]);
    return 2;
  }
  Emulator emu;
  if (argc > 2) {
    if (!strcmp(argv[2], "po300")) emu.model = EMU_PO300;
    else if (!strcmp(argv[2], "po250")) emu.model = EMU_PO250;
  }
  if (argc > 3) {
    if (strstr(argv[3], "silent")) emu.faults |= FAULT_SILENT;
    if (strstr(argv[3], "badsum")) emu.faults |= FAULT_BAD_CHECKSUM;
    if (strstr(argv[3], "split")) emu.faults |= FAULT_SPLIT;
    if (strstr(argv[3], "unpadded")) emu.faults |= FAULT_UNPADDED;
  }
  if (argc > 4) emu.model_override = argv[4];

  master_fd = posix_openpt(O_RDWR | O_NOCTTY);
  if (master_fd < 0 || grantpt(master_fd) || unlockpt(master_fd)) {
    perror("pty");
    return 1;
  }
  const char *slave = ptsname(master_fd);
  // Raw from the start, so nothing is echoed back before fiedle400 configures the port.
  int s = open(slave, O_RDWR | O_NOCTTY);
  struct termios t;
  tcgetattr(s, &t);
  cfmakeraw(&t);
  tcsetattr(s, TCSANOW, &t);
  unlink(argv[1]);
  if (symlink(slave, argv[1])) {
    perror("symlink");
    return 1;
  }
  printf("%s -> %s (%s)\n", argv[1], slave, EMU_MODELS[emu.model].name);
  fflush(stdout);
  close(s);  // not held open: fiedle400 sets TIOCEXCL, which would lock this process's fd out

  bool opened = false;
  for (;;) {
    struct pollfd pfd = {master_fd, POLLIN, 0};
    poll(&pfd, 1, 1);
    if (pfd.revents & POLLIN) {
      uint8_t buf[256];
      ssize_t k = read(master_fd, buf, sizeof buf);
      for (ssize_t i = 0; i < k; i++) emu.feed(buf[i], now_ms());
      if (k > 0) opened = true;
    } else if (pfd.revents & POLLHUP) {
      if (opened) break;  // the host closed the port
      usleep(10000);
    }
    emu.poll(now_ms());
  }
  unlink(argv[1]);
  fprintf(stderr, "commands %u, unanswered %u, destructive %u\n", emu.commands, emu.unanswered,
          emu.destructive);
  return 0;
}
