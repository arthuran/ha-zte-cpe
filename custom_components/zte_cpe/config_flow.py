"""Config flow for ZTE CPE Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback

from .client import ZTECPEAuthError, ZTECPEClient, ZTECPEClientError
from .const import CONF_URL, DEFAULT_URL, DOMAIN


class ZTECPEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZTE CPE Monitor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            password = user_input[CONF_PASSWORD]
            client = ZTECPEClient(url, password)
            try:
                info = await self.hass.async_add_executor_job(client.validate)
            except ZTECPEAuthError:
                errors["base"] = "invalid_auth"
            except ZTECPEClientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.get("model") or "ZTE CPE",
                    data={CONF_URL: url, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
