# Security Policy

ZTE CPE Monitor for Home Assistant is intentionally read-only in its initial releases.

- It authenticates through the CPE's normal local Web UI login flow.
- No reboot, SMS, band-lock, Wi-Fi, DNS, or arbitrary goform write service is exposed.
- Passwords are stored only in the Home Assistant config entry; diagnostics redact them.
- Diagnostics also redact Cell ID and LTE/5G PCI values.
- The integration performs local polling and does not send CPE data to a project cloud service.

Many ZTE CPE devices expose local management over HTTP. Use this integration only on a trusted local network or trusted VPN/tunnel.

Please use GitHub private vulnerability reporting for sensitive findings. Do not put passwords, cookies, MAC addresses, public/private IP topology, IMEI/IMSI, or exploit details in public issues.
