"""Pure-Python tests for the bundled read-only client."""

import importlib.util
from pathlib import Path
import unittest

CLIENT = Path(__file__).resolve().parents[1] / "custom_components" / "zte_cpe" / "client.py"
spec = importlib.util.spec_from_file_location("zte_cpe_client", CLIENT)
client_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_mod)


class FakeClient(client_mod.ZTECPEClient):
    def __init__(self, responses):
        self.responses = responses
        self.logged_in = True
        self.password = "dummy"
        self.base = "http://192.168.0.1"

    def _get(self, fields):
        result = {}
        for field in fields:
            if field in self.responses:
                result[field] = self.responses[field]
        return result

    def login(self):
        self.logged_in = True


class ClientTests(unittest.TestCase):
    def test_snapshot_separates_sections_and_capabilities(self):
        client = FakeClient({
            "model_name": "MC_TEST",
            "hardware_version": "HW1",
            "wa_inner_version": "FW1",
            "web_version": "WEB1",
            "lte_rsrp": "-80",
            "lte_rsrq": "-10",
            "lte_snr": "20",
            "wan_active_band": "LTE BAND 3",
            "network_type": "ENDC",
            "realtime_rx_bytes": "1024",
            "wan_connect_status": "pdp_connected",
        })
        snapshot = client.snapshot()
        self.assertEqual(snapshot["radio"]["lte_rsrp"], "-80")
        self.assertEqual(snapshot["telemetry"]["realtime_rx_bytes"], "1024")
        self.assertEqual(snapshot["capabilities"]["radio_lte"], "available")
        self.assertEqual(snapshot["capabilities"]["clients_summary"], "unavailable")

    def test_device_info_contains_no_unique_router_identifier(self):
        client = FakeClient({
            "model_name": "MC_TEST",
            "hardware_version": "HW1",
            "wa_inner_version": "FW1",
            "web_version": "WEB1",
        })
        info = client.device_info()
        self.assertEqual(set(info), {"model", "hardware_version", "firmware_version", "web_version", "api_adapter"})
        self.assertNotIn("imei", info)
        self.assertNotIn("mac", info)


if __name__ == "__main__":
    unittest.main()
