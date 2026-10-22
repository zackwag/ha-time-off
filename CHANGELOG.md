# Changelog

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
