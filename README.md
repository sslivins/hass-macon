# Macon Heat Pump Controller

Home Assistant integration for the **Macon Heat Pump Controller**. It pairs
one local controller per config entry and exposes its reported state, exact
working modes, temperatures, setpoints, diagnostics, and command controls.

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
property (`arctic-controller`), and `arctic-*` device IDs are retained as
legacy wire-format identifiers. They are not claims that this integration
supports every Macon product.

## Development

```powershell
python -m pip install -e ".[tests]"
ruff check custom_components/macon tests
mypy custom_components/macon
pytest
```

Home Assistant test dependencies are installed by the test extra. The test
extra tracks the `pymacon` repository; the integration manifest pins the
runtime dependency to `pymacon==0.1.0`.

## License

[MIT](LICENSE) © [sslivins](https://github.com/sslivins)
