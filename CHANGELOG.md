# Changelog

## [1.2.1](https://github.com/zackwag/ha-time-off/compare/v1.2.0...v1.2.1) (2026-10-22)


### Bug Fixes

* configure release-please to bump manifest.json version ([#10](https://github.com/zackwag/ha-time-off/issues/10)) ([37a1e8a](https://github.com/zackwag/ha-time-off/commit/37a1e8a14a21243044baff51150a5b3598b3dbd3))

## [1.2.0](https://github.com/zackwag/ha-time-off/compare/v1.1.1...v1.2.0) (2026-10-22)


### Features

* add brand images for integration icon ([#7](https://github.com/zackwag/ha-time-off/issues/7)) ([f65333b](https://github.com/zackwag/ha-time-off/commit/f65333bc03ff8e509a31093f04e9009bd93f54c4))


### Code Refactoring

* use homeassistant.turn_off for all domains except vacuum ([#4](https://github.com/zackwag/ha-time-off/issues/4)) ([5b11cac](https://github.com/zackwag/ha-time-off/commit/5b11cacb770e05aa180c5a55e7439be86e3f609d))

## [1.1.1](https://github.com/zackwag/ha-time-off/compare/v1.1.0...v1.1.1) (2026-10-22)


### Bug Fixes

* remove unused context param and fix inconsistent time util ([#1](https://github.com/zackwag/ha-time-off/issues/1)) ([cf18598](https://github.com/zackwag/ha-time-off/commit/cf18598634c8218735cb7a4c70a51a60e4c696a6))

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
