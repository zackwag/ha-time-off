# Changelog

## [1.1.0](https://github.com/zackwag/ha-time-off/compare/v1.0.0...v1.1.0) (2026-10-22)


### Features

* initial commit of Time Off integration ([95c33e4](https://github.com/zackwag/ha-time-off/commit/95c33e4a325fb5a56ef5c023319df71ac401f545))


### Code Refactoring

* dict lookup for turn-off services, extract binary sensor closures to methods ([#2](https://github.com/zackwag/ha-time-off/issues/2)) ([dedbef2](https://github.com/zackwag/ha-time-off/commit/dedbef23d8ae557998f3c41486b1111e5fa9fdc1))

## 1.0.0

### Features

- Auto-off timers for Home Assistant devices (lights, fans, switches, covers, climate, media players, and more)
- Configurable default duration per device (0-1440 minutes)
- Trigger Only mode: fire an event on expiry without turning the device off
- Timer Active binary sensor with expiry timestamp and remaining time attributes
- Off After diagnostic sensor showing the active countdown duration
- Services: `start_timer`, `stop_timer`, `set_off_after`
- Device trigger for automations: "When timer expires"
- Timer persistence and recovery across HA restarts
- Automatic entity rename tracking
