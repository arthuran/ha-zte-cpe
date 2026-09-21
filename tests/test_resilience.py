"""Tests for transient-failure resilience policy."""

import importlib.util
from pathlib import Path
import unittest

POLLING = Path(__file__).resolve().parents[1] / "custom_components" / "zte_cpe" / "polling.py"
spec = importlib.util.spec_from_file_location("zte_cpe_polling_resilience", POLLING)
polling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(polling)


class ResiliencePolicyTests(unittest.TestCase):
    def test_transient_failure_grace_is_two_polls(self):
        self.assertEqual(polling.TRANSIENT_FAILURE_GRACE, 2)
        self.assertTrue(1 <= polling.TRANSIENT_FAILURE_GRACE)
        self.assertTrue(2 <= polling.TRANSIENT_FAILURE_GRACE)
        self.assertFalse(3 <= polling.TRANSIENT_FAILURE_GRACE)

    def test_failure_retry_delays_do_not_hammer_cpe(self):
        self.assertGreaterEqual(polling.failure_backoff_seconds(1), 120)
        self.assertGreaterEqual(polling.failure_backoff_seconds(2), 240)
        self.assertLessEqual(polling.failure_backoff_seconds(20), 900)


if __name__ == "__main__":
    unittest.main()
