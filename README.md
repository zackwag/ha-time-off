# Time Off

A Home Assistant custom integration that automatically turns off devices after a configurable duration.

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
1. Search for "Time Off" and install
1. Restart Home Assistant

### Manual

Copy `custom_components/time_off/` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

Go to **Settings > Devices & Services > Add Integration** and search for **Time Off**. Select the device you want to manage.

## How it works

When a managed device turns on, Time Off starts a countdown. When the countdown expires:

- **Auto-Off mode** (default): turns the device off and fires `time_off_timer_expired`
- **Trigger Only mode**: fires `time_off_timer_expired` without touching the device, then re-arms for another cycle

## Entities

Each managed device gets four helper entities on its device card:

| Entity | Type | Description |
|---|---|---|
| Time Off | Number | Default countdown duration in minutes. Set to 0 to disable. |
| Off After | Sensor | Read-only display of the active countdown duration. |
| Timer Active | Binary sensor | ON while a countdown is running. Attributes: `expiry`, `remaining`. |
| Trigger Only | Switch | Toggle between Auto-Off and Trigger Only mode. |

## Services

| Service | Description |
|---|---|
| `time_off.start_timer` | Start or restart the countdown for a managed device. |
| `time_off.stop_timer` | Cancel the countdown without turning the device off. |
| `time_off.set_off_after` | Set a custom duration (0-1440 min) and restart the timer. |

All services target the managed device entity (e.g. `fan.bathroom_fan`), not the Time Off helper entities.

## Supported domains

switch, light, fan, media_player, cover, climate, input_boolean, humidifier, siren, valve, vacuum
