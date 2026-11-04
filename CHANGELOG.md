# Changelog

## Unreleased

- **Expansion valve sensors now read 10x higher.** Arctic controller firmware
  3.8.0 reports the main and aux EEV openings in real motor steps (0-500)
  instead of the mainboard's steps / 10. The entities keep the `steps` unit;
  history recorded before the controller upgrade is 10x lower. No change is
  needed in this integration's code - values pass through unchanged.
