# ZTE CPE Monitor for Home Assistant

Read-only Home Assistant integration for compatible ZTE CPE devices.

The initial release focuses on radio quality, connection state, traffic counters and privacy-conscious diagnostics. It uses Home Assistant config entries and a shared `DataUpdateCoordinator` so all entities are refreshed in one coordinated poll.

## Current features

- UI setup through Config Flow
- adaptive local polling: 60s normally, 30s after meaningful radio/network changes, 120s when stable
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

## Adaptive polling

The integration is designed to reduce continuous load on low-resource CPE hardware:

- **60 seconds** under normal conditions
- **30 seconds** temporarily after a meaningful band/channel/network-state change or a significant signal change
- **120 seconds** after the connection remains stable for several polls
- failures use exponential retry backoff: **120s → 240s → 480s → 900s maximum**

Normal traffic-counter increments do not trigger fast polling, otherwise active traffic would keep the CPE at the fastest cadence indefinitely. The existing authenticated session is reused while valid instead of logging in on every poll.

Transient request failures are tolerated for two polling cycles: Home Assistant keeps the last-known values and exposes `Data Fresh` as off instead of immediately marking every entity unavailable. A persistent failure still becomes unavailable after the grace period. Expired Web UI sessions are automatically re-authenticated.

Partial responses are also handled per field. If one value such as 5G RSRP is temporarily empty while the rest of the poll succeeds, its last-known value is retained for up to three successful polls and that entity reports `data_stale: true`. If the field remains empty beyond that grace window, it becomes unavailable normally so stale radio data is never retained indefinitely.

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
