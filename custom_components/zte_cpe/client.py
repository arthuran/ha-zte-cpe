"""Small read-only ZTE CPE client for the Home Assistant integration.

This module intentionally mirrors the tested legacy-goform-ld adapter from
zte-cpe-monitor until the protocol client is published as a shared package.
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEVICE_INFO_FIELDS = [
    "model_name", "product_name", "device_name", "hardware_version",
    "wa_inner_version", "cr_version", "web_version", "network_type",
]

RADIO_FIELDS = [
    "wan_active_channel", "wan_active_band",
    "lte_rssi", "lte_rsrp", "lte_snr", "lte_rsrq", "lte_pci", "cell_id",
    "nr5g_action_channel", "nr5g_action_band", "Z5g_rsrp", "Z5g_SINR",
    "nr5g_pci", "wan_lte_ca", "lte_multi_ca_scell_info",
    "network_type", "signalbar",
]

TELEMETRY_FIELDS = [
    "wan_connect_status", "ppp_status", "realtime_time",
    "realtime_tx_bytes", "realtime_rx_bytes", "realtime_tx_thrpt", "realtime_rx_thrpt",
    "monthly_tx_bytes", "monthly_rx_bytes", "monthly_time",
]

CAPABILITY_GROUPS = {
    "radio_lte": ["wan_active_channel", "wan_active_band", "lte_rsrp", "lte_rsrq", "lte_snr", "lte_pci"],
    "radio_nr5g": ["nr5g_action_channel", "nr5g_action_band", "Z5g_rsrp", "Z5g_SINR", "nr5g_pci"],
    "radio_ca": ["wan_lte_ca", "lte_multi_ca_scell_info"],
    "network_connection": ["wan_connect_status", "ppp_status", "realtime_time"],
    "traffic_realtime": ["realtime_tx_bytes", "realtime_rx_bytes", "realtime_tx_thrpt", "realtime_rx_thrpt"],
    "traffic_monthly": ["monthly_tx_bytes", "monthly_rx_bytes", "monthly_time"],
    "clients_summary": [
        "wifi_access_sta_num", "wifi_chip1_ssid1_access_sta_num", "wifi_chip2_ssid1_access_sta_num",
        "wifi_chip1_ssid2_access_sta_num", "wifi_chip2_ssid2_access_sta_num",
    ],
}


class ZTECPEClientError(RuntimeError):
    """Base client error."""


class ZTECPEAuthError(ZTECPEClientError):
    """Authentication failed."""


def _sha256_upper(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


class ZTECPEClient:
    """Synchronous read-only client for legacy ZTE goform firmware."""

    def __init__(self, url: str, password: str, timeout: int = 8) -> None:
        self.base = url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.lock = threading.Lock()
        self.logged_in = False

    def _request(
        self,
        path: str,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Referer": self.base + "/",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "ha-zte-cpe/0.1.1",
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.URLError as exc:
            raise ZTECPEClientError(f"Unable to reach ZTE CPE: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ZTECPEClientError("ZTE CPE returned a non-JSON response") from exc

    def _get(self, fields: list[str]) -> dict[str, Any]:
        return self._request(
            "/goform/goform_get_cmd_process",
            {"isTest": "false", "multi_data": "1", "cmd": ",".join(fields)},
        )

    def login(self) -> None:
        """Authenticate using the legacy LD challenge-response flow."""
        with self.lock:
            ld = self._get(["LD"]).get("LD", "")
            if not ld:
                raise ZTECPEAuthError("Unable to read the LD challenge")
            signature = _sha256_upper(_sha256_upper(self.password) + ld)
            result = self._request(
                "/goform/goform_set_cmd_process",
                data={"isTest": "false", "goformId": "LOGIN", "password": signature},
            )
            if str(result.get("result")) != "0":
                raise ZTECPEAuthError("Authentication failed")
            self.logged_in = True

    def _ensure_login(self) -> None:
        if not self.logged_in:
            self.login()

    def validate(self) -> dict[str, Any]:
        """Validate credentials and return safe device metadata."""
        self.login()
        return self.device_info()

    def device_info(self) -> dict[str, Any]:
        self._ensure_login()
        raw = self._get(DEVICE_INFO_FIELDS)
        model = raw.get("model_name") or raw.get("product_name") or raw.get("device_name") or "ZTE CPE"
        return {
            "model": model,
            "hardware_version": raw.get("hardware_version") or "",
            "firmware_version": raw.get("wa_inner_version") or raw.get("cr_version") or "",
            "web_version": raw.get("web_version") or "",
            "api_adapter": "legacy-goform-ld",
        }

    def snapshot(self) -> dict[str, Any]:
        """Fetch all data required by Home Assistant in coordinated requests."""
        self._ensure_login()
        fields = []
        for field in RADIO_FIELDS + TELEMETRY_FIELDS:
            if field not in fields:
                fields.append(field)
        for group in CAPABILITY_GROUPS.values():
            for field in group:
                if field not in fields:
                    fields.append(field)

        raw = self._get(fields)
        if not any(raw.get(key) not in (None, "") for key in ("lte_rsrp", "Z5g_rsrp", "network_type")):
            self.logged_in = False
            self.login()
            raw = self._get(fields)

        capabilities: dict[str, str] = {}
        for name, group in CAPABILITY_GROUPS.items():
            present = [field for field in group if field in raw]
            nonempty = [field for field in group if raw.get(field) not in (None, "")]
            capabilities[name] = "available" if nonempty else ("present-empty" if present else "unavailable")

        return {
            "device": self.device_info(),
            "radio": {field: raw.get(field, "") for field in RADIO_FIELDS},
            "telemetry": {field: raw.get(field, "") for field in TELEMETRY_FIELDS},
            "capabilities": capabilities,
        }
