"""Tests for adaptive polling policy."""

import importlib.util
from pathlib import Path
import unittest

POLLING = Path(__file__).resolve().parents[1] / "custom_components" / "zte_cpe" / "polling.py"
spec = importlib.util.spec_from_file_location("zte_cpe_polling", POLLING)
polling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(polling)


def snap(*, rsrp="-80", sinr="20", band="LTE BAND 3", channel="1275", wan="pdp_connected"):
    return {
        "radio": {
            "lte_rsrp": rsrp,
            "lte_snr": sinr,
            "wan_active_band": band,
            "wan_active_channel": channel,
            "network_type": "ENDC",
            "signalbar": "5",
        },
        "telemetry": {
            "wan_connect_status": wan,
            "ppp_status": "ppp_connected",
            # Traffic changes must not affect adaptive cadence.
            "realtime_rx_bytes": "1000",
        },
    }


class PollingPolicyTests(unittest.TestCase):
    def test_first_poll_defaults_to_sixty_seconds(self):
        interval, stable = polling.next_success_interval(None, snap(), 0, 60)
        self.assertEqual((interval, stable), (60, 0))

    def test_significant_signal_change_switches_to_fast_polling(self):
        interval, stable = polling.next_success_interval(snap(rsrp="-80"), snap(rsrp="-76"), 5, 120)
        self.assertEqual((interval, stable), (30, 0))

    def test_small_signal_jitter_does_not_switch_to_fast_polling(self):
        interval, stable = polling.next_success_interval(snap(rsrp="-80"), snap(rsrp="-79"), 0, 60)
        self.assertEqual((interval, stable), (60, 1))

    def test_band_or_connection_change_switches_to_fast_polling(self):
        self.assertTrue(polling.has_meaningful_change(snap(), snap(band="LTE BAND 1")))
        self.assertTrue(polling.has_meaningful_change(snap(), snap(wan="disconnected")))

    def test_traffic_counter_changes_are_ignored(self):
        previous = snap()
        current = snap()
        current["telemetry"]["realtime_rx_bytes"] = "99999999"
        self.assertFalse(polling.has_meaningful_change(previous, current))

    def test_fast_polling_relaxes_after_three_stable_polls(self):
        previous = snap()
        current = snap()
        interval, stable = polling.next_success_interval(previous, current, 0, 30)
        self.assertEqual((interval, stable), (30, 1))
        interval, stable = polling.next_success_interval(previous, current, stable, interval)
        self.assertEqual((interval, stable), (30, 2))
        interval, stable = polling.next_success_interval(previous, current, stable, interval)
        self.assertEqual((interval, stable), (60, 3))

    def test_stable_device_relaxes_to_120_seconds(self):
        interval, stable = polling.next_success_interval(snap(), snap(), 7, 60)
        self.assertEqual((interval, stable), (120, 8))

    def test_failure_backoff_is_exponential_and_capped(self):
        self.assertEqual(polling.failure_backoff_seconds(1), 120)
        self.assertEqual(polling.failure_backoff_seconds(2), 240)
        self.assertEqual(polling.failure_backoff_seconds(3), 480)
        self.assertEqual(polling.failure_backoff_seconds(20), 900)


if __name__ == "__main__":
    unittest.main()
