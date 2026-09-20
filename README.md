# ZTE CPE Monitor for Home Assistant

Read-only Home Assistant integration for compatible ZTE CPE devices.

The initial release focuses on radio quality, connection state, traffic counters and privacy-conscious diagnostics. It uses Home Assistant config entries and a shared `DataUpdateCoordinator` so all entities are refreshed in one coordinated poll.

## Current features

- UI setup through Config Flow
- local polling every 30 seconds
- LTE RSRP / RSRQ / SINR / band
- 5G RSRP / SINR / band
- signal bars
- WAN and PPP connected binary sensors
- connection/session time
- realtime TX/RX totals and rates
- monthly TX/RX totals and connected time
- firmware/model metadata in the HA device registry
- privacy-conscious diagnostics
- English and Thai setup strings

## Compatibility

The first adapter implements the `legacy-goform-ld` API family and has been tested against ZTE MC7010 firmware in that family. Other models using the same authentication and field names may work, but are not yet qualified.

Client tracking is capability-driven. Some ZTE routers expose LAN/WLAN client lists; outdoor CPE models may expose no local clients because downstream devices are behind another router.

## Installation

### HACS custom repository

Until listed in the default HACS repository catalog, add this repository as a custom integration repository and install **ZTE CPE Monitor**.

### Manual

Copy:

```text
custom_components/zte_cpe
```

into your Home Assistant configuration directory under:

```text
/config/custom_components/zte_cpe
```

Restart Home Assistant, then open **Settings → Devices & services → Add integration → ZTE CPE Monitor**.

## Security

This integration is read-only by design. It does not expose generic router write commands. See [SECURITY.md](SECURITY.md).

## Related project

CLI and temporary dashboard: https://github.com/arthuran/zte-cpe-monitor

## License

MIT
