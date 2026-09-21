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
        self.reauth_count = 0
        self._device_info_cache = None
        self.jar = __import__("http.cookiejar").cookiejar.CookieJar()

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


class SessionRecoveryTests(unittest.TestCase):
    def test_snapshot_reauthenticates_after_expired_non_json_session(self):
        class ExpiringClient(FakeClient):
            def __init__(self):
                super().__init__({
                    "model_name": "MC_TEST",
                    "hardware_version": "HW1",
                    "wa_inner_version": "FW1",
                    "web_version": "WEB1",
                    "lte_rsrp": "-80",
                    "network_type": "ENDC",
                    "wan_connect_status": "pdp_connected",
                })
                self.fail_next_get = True
                self.login_calls = 0
                self.jar = __import__("http.cookiejar").cookiejar.CookieJar()

            def _get(self, fields):
                if self.fail_next_get:
                    self.fail_next_get = False
                    raise client_mod.ZTECPEProtocolError("ZTE CPE returned a non-JSON response")
                return super()._get(fields)

            def login(self):
                self.login_calls += 1
                self.logged_in = True

        client = ExpiringClient()
        snapshot = client.snapshot()
        self.assertEqual(client.login_calls, 1)
        self.assertEqual(snapshot["radio"]["lte_rsrp"], "-80")
        self.assertTrue(client.logged_in)

    def test_empty_expired_payload_also_triggers_reauthentication(self):
        class EmptyOnceClient(FakeClient):
            def __init__(self):
                super().__init__({
                    "model_name": "MC_TEST",
                    "lte_rsrp": "-80",
                    "network_type": "ENDC",
                })
                self.empty_once = True
                self.login_calls = 0
                self.jar = __import__("http.cookiejar").cookiejar.CookieJar()

            def _get(self, fields):
                if self.empty_once:
                    self.empty_once = False
                    return {field: "" for field in fields}
                return super()._get(fields)

            def login(self):
                self.login_calls += 1
                self.logged_in = True

        client = EmptyOnceClient()
        snapshot = client.snapshot()
        self.assertEqual(client.login_calls, 0)
        self.assertEqual(snapshot["radio"]["lte_rsrp"], "-80")


class PartialFieldRetryTests(unittest.TestCase):
    def test_missing_critical_radio_field_is_retried_targetedly(self):
        class PartialClient(FakeClient):
            def __init__(self):
                super().__init__({
                    "model_name": "MC_TEST",
                    "hardware_version": "HW1",
                    "wa_inner_version": "FW1",
                    "web_version": "WEB1",
                    "lte_rsrp": "-50",
                    "wan_active_band": "LTE BAND 3",
                    "network_type": "ENDC",
                    "Z5g_rsrp": "-67",
                    "nr5g_action_band": "n41",
                    "wan_connect_status": "pdp_connected",
                    "ppp_status": "ppp_connected",
                })
                self.calls = []
                self.first_radio = True

            def _get(self, fields):
                self.calls.append(tuple(fields))
                result = super()._get(fields)
                if self.first_radio and "Z5g_rsrp" in fields and len(fields) > 1:
                    self.first_radio = False
                    result["Z5g_rsrp"] = ""
                return result

        client = PartialClient()
        snapshot = client.snapshot()
        self.assertEqual(snapshot["radio"]["Z5g_rsrp"], "-67")
        self.assertIn(("Z5g_rsrp",), client.calls)

    def test_snapshot_uses_separate_radio_and_telemetry_requests(self):
        class RecordingClient(FakeClient):
            def __init__(self):
                super().__init__({
                    "model_name": "MC_TEST",
                    "hardware_version": "HW1",
                    "wa_inner_version": "FW1",
                    "web_version": "WEB1",
                    "lte_rsrp": "-50",
                    "wan_active_band": "LTE BAND 3",
                    "network_type": "ENDC",
                    "Z5g_rsrp": "-67",
                    "nr5g_action_band": "n41",
                    "wan_connect_status": "pdp_connected",
                    "ppp_status": "ppp_connected",
                })
                self.calls = []

            def _get(self, fields):
                self.calls.append(tuple(fields))
                return super()._get(fields)

        client = RecordingClient()
        client.snapshot()
        self.assertIn(tuple(client_mod.RADIO_FIELDS), client.calls)
        self.assertIn(tuple(client_mod.TELEMETRY_FIELDS), client.calls)
        self.assertNotIn(tuple(client_mod.RADIO_FIELDS + client_mod.TELEMETRY_FIELDS), client.calls)


class WholeSnapshotRecoveryTests(unittest.TestCase):
    def test_completely_empty_snapshot_reauthenticates_once(self):
        class EmptySnapshotClient(FakeClient):
            def __init__(self):
                super().__init__({
                    "model_name": "MC_TEST",
                    "hardware_version": "HW1",
                    "wa_inner_version": "FW1",
                    "web_version": "WEB1",
                    "lte_rsrp": "-50",
                    "wan_active_band": "LTE BAND 3",
                    "network_type": "ENDC",
                    "Z5g_rsrp": "-67",
                    "nr5g_action_band": "n41",
                    "wan_connect_status": "pdp_connected",
                    "ppp_status": "ppp_connected",
                })
                self.login_calls = 0
                self.empty_groups_remaining = 4

            def _get(self, fields):
                if self.empty_groups_remaining > 0:
                    self.empty_groups_remaining -= 1
                    return {field: "" for field in fields}
                return super()._get(fields)

            def login(self):
                self.login_calls += 1
                self.logged_in = True

        client = EmptySnapshotClient()
        snapshot = client.snapshot()
        self.assertEqual(client.login_calls, 1)
        self.assertEqual(snapshot["radio"]["lte_rsrp"], "-50")
        self.assertEqual(snapshot["telemetry"]["wan_connect_status"], "pdp_connected")
