# Macon Heat Pump Controller

Home Assistant integration for the
[**Arctic Controller**](https://github.com/sslivins/arctic-controller) — a
custom, self-built controller for Macon heat pumps. It talks to the Arctic
Controller hardware/firmware, **not** the OEM Macon controller, and is not
affiliated with or endorsed by Macon. It pairs one local controller per config
entry and exposes its reported state, exact working modes, temperatures,
setpoints, diagnostics, and command controls.

> **Compatibility:** This integration only works with the
> [Arctic Controller](https://github.com/sslivins/arctic-controller) (the
> DIY/self-built controller). It does not support the stock OEM Macon
> controller.

The integration uses [`pymacon`](https://github.com/sslivins/pymacon) for
pinned-TLS REST and WebSocket transport. Commands are not optimistic:
Home Assistant updates only from controller-reported snapshots.

## Install with HACS

1. Open HACS and add `sslivins/hass-macon` as a custom integration repository.
2. Install **Macon Heat Pump Controller**.
3. Restart Home Assistant.
4. Add the integration from **Settings → Devices & services**.

## Manual install

Copy `custom_components/macon/` into the `custom_components/` directory of
your Home Assistant configuration, restart Home Assistant, and add the
integration.

## Discovery and compatibility

Physical pairing verifies the displayed one-time code and SHA-256 TLS
fingerprint. Multiple controllers are isolated from one another, and
credential or certificate changes trigger reauthentication.

The firmware's zeroconf service type (`_arctic._tcp.local.`), discovery
property (`arctic-controller`), and `arctic-*` device IDs are the Arctic
Controller's own wire-format identifiers. This integration targets the Arctic
Controller only and makes no claim to support OEM Macon controllers.

## Sensors and fault reporting

Alongside the climate control and the operational sensors (tank/outlet/inlet
temperatures, setpoints, power, COP, and — as diagnostic entities — compressor
frequency, fan speed/level, and the refrigerant-circuit temperatures), the
integration exposes a **Fault code** sensor. Its state is the stable Arctic
Controller fault code (for example `P02`) of the highest-severity active fault,
`ok` when the unit is healthy, or `unknown` for an unrecognised code. The
human-readable text is available on the sensor's `description` attribute, and
Home Assistant's own History/Logbook provides the fault timeline.

A `macon_fault` event is fired whenever a fault begins, clears, or changes:

```yaml
event_type: macon_fault
data:
  device_id: arctic-xxxxxxxx
  active: true
  code: P02
  name: HIGH_PRESSURE
  description: High pressure protection activated
  severity: critical
```

When a fault clears, `active` is `false` and `code` is `null`. Use the event in
automations to send a notification with the exact code and description.

## Development

```powershell
python -m pip install -e ".[tests]"
ruff check custom_components/macon tests
mypy custom_components/macon
pytest
```

Home Assistant test dependencies are installed by the test extra. The test
extra tracks the `pymacon` repository; the integration manifest pins the
runtime dependency to `pymacon==0.2.2`.

## License

[MIT](LICENSE) © [sslivins](https://github.com/sslivins)
