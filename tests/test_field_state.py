"""Tests for field-level partial response resilience."""

import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "zte_cpe" / "field_state.py"
spec = importlib.util.spec_from_file_location("zte_cpe_field_state", MODULE)
field_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field_state)


def snapshot(*, nr_rsrp="-70", nr_sinr="25", lte_rsrp="-50", rx="100"):
    return {
        "device": {"model": "MC_TEST"},
        "radio": {
            "Z5g_rsrp": nr_rsrp,
            "Z5g_SINR": nr_sinr,
            "lte_rsrp": lte_rsrp,
            "network_type": "ENDC",
        },
        "telemetry": {"realtime_rx_bytes": rx},
        "capabilities": {"radio_nr5g": "available"},
    }


class FieldStateTests(unittest.TestCase):
    def test_single_empty_5g_field_keeps_last_good_value(self):
        previous = snapshot(nr_rsrp="-68")
        current = snapshot(nr_rsrp="")
        merged, counts, stale = field_state.merge_snapshot_fields(previous, current, {})
        self.assertEqual(merged["radio"]["Z5g_rsrp"], "-68")
        self.assertEqual(counts["radio.Z5g_rsrp"], 1)
        self.assertEqual(stale, {"radio.Z5g_rsrp"})
        self.assertEqual(merged["radio"]["Z5g_SINR"], "25")

    def test_fresh_field_immediately_clears_stale_marker(self):
        previous = snapshot(nr_rsrp="-68")
        current = snapshot(nr_rsrp="-72")
        merged, counts, stale = field_state.merge_snapshot_fields(
            previous, current, {"radio.Z5g_rsrp": 2}
        )
        self.assertEqual(merged["radio"]["Z5g_rsrp"], "-72")
        self.assertNotIn("radio.Z5g_rsrp", counts)
        self.assertNotIn("radio.Z5g_rsrp", stale)

    def test_field_expires_after_three_successful_empty_polls(self):
        current = snapshot(nr_rsrp="")
        merged = snapshot(nr_rsrp="-68")
        counts = {}
        for expected in (1, 2, 3):
            merged, counts, stale = field_state.merge_snapshot_fields(merged, current, counts)
            self.assertEqual(merged["radio"]["Z5g_rsrp"], "-68")
            self.assertEqual(counts["radio.Z5g_rsrp"], expected)
            self.assertIn("radio.Z5g_rsrp", stale)
        merged, counts, stale = field_state.merge_snapshot_fields(merged, current, counts)
        self.assertEqual(merged["radio"]["Z5g_rsrp"], "")
        self.assertNotIn("radio.Z5g_rsrp", counts)
        self.assertNotIn("radio.Z5g_rsrp", stale)

    def test_initially_empty_unsupported_field_is_not_fake_stale_data(self):
        merged, counts, stale = field_state.merge_snapshot_fields(None, snapshot(nr_rsrp=""), {})
        self.assertEqual(merged["radio"]["Z5g_rsrp"], "")
        self.assertEqual(counts, {})
        self.assertEqual(stale, set())

    def test_fields_are_retained_independently(self):
        previous = snapshot(nr_rsrp="-68", nr_sinr="24", rx="100")
        current = snapshot(nr_rsrp="", nr_sinr="26", rx="")
        merged, counts, stale = field_state.merge_snapshot_fields(previous, current, {})
        self.assertEqual(merged["radio"]["Z5g_rsrp"], "-68")
        self.assertEqual(merged["radio"]["Z5g_SINR"], "26")
        self.assertEqual(merged["telemetry"]["realtime_rx_bytes"], "100")
        self.assertEqual(stale, {"radio.Z5g_rsrp", "telemetry.realtime_rx_bytes"})
        self.assertEqual(set(counts), stale)


if __name__ == "__main__":
    unittest.main()
