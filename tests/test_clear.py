"""`clear` erases with SpO2 Assistant's own commands (T-037, PROTOCOL.md 3.13), checked against the
vendor capture. The simulator never erases anything: it records the attempt in
`FakeOximeter.destructive`, so the recording is still listed afterwards and `clear` reports that."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwsim import command_key  # noqa: E402
import test_hwsim_linux as base  # noqa: E402
import test_manual_mode as manual_base  # noqa: E402

from fiedle400.protocol import Commands  # noqa: E402
from fiedle400.protocol import manual  # noqa: E402


class TestBytes(unittest.TestCase):
    def test_delete_all_is_byte_for_byte_the_vendors(self):
        vendor = [o for o, _, _ in base.trace().groups if o[:2] == b"\x9d\x7f"]
        self.assertTrue(vendor)
        self.assertEqual({bytes(o) for o in vendor}, {Commands.delete_all()})
        self.assertEqual(Commands.delete_all()[:8].hex(" "), "9d 7f 7f 7f 7f 00 00 19")

    def test_delete_one_names_series_user_and_entry(self):
        self.assertEqual(Commands.delete_entry(1, 3)[:8], bytes([0x9D, 0x7F, 0x02, 1, 3, 0, 0, (0x9D + 0x7F + 2 + 1 + 3) & 0x7F]))
        self.assertEqual(Commands.delete_entry(1, 3, 1)[:3], bytes([0x9D, 0x7F, 0x01]))

    def test_both_count_as_destructive_in_the_simulator(self):
        for cmd in (Commands.delete_all(), Commands.delete_entry(1, 1)):
            self.assertEqual(command_key(cmd), ("destructive", 0x9D))


class TestEraseReply(unittest.TestCase):
    def test_the_vendor_captures_erase_reply_reads_as_done(self):
        # bum400_raw.pcapng / bum400.pcapng: the device answers 9D 7F 7F 7F 7F with ED 7F 7F 7F 7F 00 69.
        from fiedle400.engine.device import SerialDeviceEngine
        reports = [bytes.fromhex("ef 00 00 00 00 00 00 6f ed 7f 7f 7f 7f 00 69") + bytes(49)]
        eng = SerialDeviceEngine.__new__(SerialDeviceEngine)
        eng.dev = type("D", (), {"read_report": lambda self, n: reports.pop(0) if reports else b""})()
        self.assertEqual(eng._erase_status(), 0)


class TestClear(base.FlowCase):
    def test_clear_all_lists_opens_the_transfer_then_deletes_all(self):
        ok = self.engine.clear_memory(0)
        self.assertEqual(self.fake.destructive, [Commands.delete_all()])
        keys = [command_key(r) for r in self.fake.sent]
        i = keys.index(("destructive", 0x9D))
        self.assertEqual(keys[i - 1], (0x9D, 2))
        self.assertFalse(ok)  # the simulator did not erase, and clear noticed

    def test_clear_one_deletes_pulse_then_spo2_of_that_user_and_entry(self):
        self.engine.clear_memory(1)
        self.assertEqual(self.fake.destructive, [Commands.delete_entry(1, 1, 2), Commands.delete_entry(1, 1, 1)])

    def test_clear_one_stops_when_the_device_reports_a_failed_erase(self):
        frame = [0xED, 0x7F, 0x02, 1, 1, 0x05]
        failed = bytes(frame + [sum(frame) & 0x7F] + [0] * 57)
        real_read = self.engine.dev.read_report
        sent = []

        def read_report(n):
            if self.fake.destructive and not sent:
                sent.append(1)
                return failed
            return real_read(n)
        self.engine.dev.read_report = read_report
        self.engine.clear_memory(1)
        self.assertEqual(self.fake.destructive, [Commands.delete_entry(1, 1, 2)])

    def test_nothing_is_sent_for_a_session_that_does_not_exist(self):
        self.engine.clear_memory(7)
        self.assertEqual(self.fake.destructive, [])

    def test_no_old_candidate_opcodes_are_sent(self):
        self.engine.clear_memory(0)
        self.assertFalse({0xAA, 0xAB, 0xAC, 0xAF, 0x91, 0x92, 0x93, 0x95, 0x96} & set(self.fake.opcodes_sent()))


class TestClearManual(manual_base.ManualFlow):
    """A Manual-mode recording is erased with `A1`, not `9D 7F` (PROTOCOL.md 3.14 G, T-072).

    Non-strict: `clear_memory` re-asks the header afterwards to verify, and the fixture only
    recorded one `0xA0` exchange; non-strict repeats that last recorded reply, as the device
    itself would for an unchanged recording."""

    def make_fake(self):
        return manual_base.FakeOximeter(manual_base.trace())

    def test_clear_sends_a1_00_then_a1_01_and_no_9d(self):
        ok = self.engine.clear_memory(1)
        self.assertEqual(self.fake.destructive, [manual.delete_step(0), manual.delete_step(1)])
        self.assertFalse(ok)  # the simulator did not erase, and clear noticed
        self.assertNotIn(0x9D, self.fake.opcodes_sent())

    def test_clear_all_also_takes_the_manual_path(self):
        self.engine.clear_memory(0)
        self.assertEqual(self.fake.destructive, [manual.delete_step(0), manual.delete_step(1)])

    def test_a1_04_is_never_sent(self):
        self.engine.clear_memory(1)
        self.assertEqual(self.fake.destructive, [manual.delete_step(0), manual.delete_step(1)])


if __name__ == "__main__":
    unittest.main()
