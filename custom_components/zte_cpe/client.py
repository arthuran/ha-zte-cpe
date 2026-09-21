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


class ZTECPETransportError(ZTECPEClientError):
    """Transport-level request failure."""


class ZTECPEProtocolError(ZTECPEClientError):
    """Unexpected/non-JSON protocol response."""


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
        self.reauth_count = 0
        self._device_info_cache: dict[str, Any] | None = None

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
                "User-Agent": "ha-zte-cpe/0.1.4",
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ZTECPETransportError(f"Unable to reach ZTE CPE: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ZTECPEProtocolError("ZTE CPE returned a non-JSON response") from exc

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

    def invalidate_session(self) -> None:
        """Forget local authentication state so the next request logs in again."""
        self.logged_in = False
        self.jar.clear()

    def _reauthenticate(self) -> None:
        """Start a fresh Web UI session after a protocol-level expiry."""
        self.invalidate_session()
        self.login()
        self.reauth_count += 1

    def _authenticated_get(
        self,
        fields: list[str],
        meaningful_fields: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Read fields and recover once if the CPE session expired.

        Some ZTE firmware returns the login page (non-JSON) after its Web UI
        session expires.  Keeping only a local ``logged_in`` boolean would
        otherwise leave the integration stuck until it was manually reloaded.
        """
        self._ensure_login()
        try:
            raw = self._get(fields)
        except ZTECPEProtocolError:
            self._reauthenticate()
            return self._get(fields)

        if meaningful_fields and not any(
            raw.get(field) not in (None, "") for field in meaningful_fields
        ):
            self._reauthenticate()
            return self._get(fields)
        return raw

    def validate(self) -> dict[str, Any]:
        """Validate credentials and return safe device metadata."""
        self.login()
        return self.device_info()

    def _device_info_from_raw(self, raw: dict[str, Any]) -> dict[str, Any]:
        model = raw.get("model_name") or raw.get("product_name") or raw.get("device_name") or "ZTE CPE"
        return {
            "model": model,
            "hardware_version": raw.get("hardware_version") or "",
            "firmware_version": raw.get("wa_inner_version") or raw.get("cr_version") or "",
            "web_version": raw.get("web_version") or "",
            "api_adapter": "legacy-goform-ld",
        }

    def device_info(self) -> dict[str, Any]:
        if self._device_info_cache is not None:
            return dict(self._device_info_cache)
        raw = self._authenticated_get(
            DEVICE_INFO_FIELDS,
            ("model_name", "product_name", "device_name"),
        )
        self._device_info_cache = self._device_info_from_raw(raw)
        return dict(self._device_info_cache)

    def snapshot(self) -> dict[str, Any]:
        """Fetch all data required by Home Assistant in coordinated requests."""
        fields = []
        for field in RADIO_FIELDS + TELEMETRY_FIELDS + DEVICE_INFO_FIELDS:
            if field not in fields:
                fields.append(field)
        for group in CAPABILITY_GROUPS.values():
            for field in group:
                if field not in fields:
                    fields.append(field)

        raw = self._authenticated_get(
            fields,
            ("lte_rsrp", "Z5g_rsrp", "network_type"),
        )

        if self._device_info_cache is None:
            self._device_info_cache = self._device_info_from_raw(raw)

        capabilities: dict[str, str] = {}
        for name, group in CAPABILITY_GROUPS.items():
            present = [field for field in group if field in raw]
            nonempty = [field for field in group if raw.get(field) not in (None, "")]
            capabilities[name] = "available" if nonempty else ("present-empty" if present else "unavailable")

        return {
            "device": dict(self._device_info_cache),
            "radio": {field: raw.get(field, "") for field in RADIO_FIELDS},
            "telemetry": {field: raw.get(field, "") for field in TELEMETRY_FIELDS},
            "capabilities": capabilities,
        }
