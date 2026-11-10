# Changelog

## 0.16.0

- **Loop supply, return and water delta T sensors.** Arctic controller
  firmware 3.11.0 publishes the loop water temperatures the COP uses (the
  external pipe sensors when configured, else the unit's outlet/inlet).
  Supply/Return temperature report even while idle; Water delta T is
  `unknown` whenever the pump is off. Older firmware leaves all three
  `unknown`. Requires pymacon 0.5.7.

## 0.15.1

- **Expansion valve sensors now read 10x higher.** Arctic controller firmware
  3.8.0 reports the main and aux EEV openings in real motor steps (0-500)
  instead of the mainboard's steps / 10. The entities keep the `steps` unit;
  history recorded before the controller upgrade is 10x lower. No change is
  needed in this integration's code - values pass through unchanged.
