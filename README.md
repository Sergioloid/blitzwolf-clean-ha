<p align="center">
  <img src="icon.png" alt="BlitzWolf Vacuum" width="128">
</p>

<h1 align="center">BlitzWolf Vacuum - Home Assistant Integration</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/Sergioloid/blitzwolf-clean-ha/releases"><img src="https://img.shields.io/github/v/release/Sergioloid/blitzwolf-clean-ha" alt="Release"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
</p>

Custom Home Assistant integration for **BlitzWolf BW-VC1** robot vacuum cleaners (and compatible Slamtec/Lambot-based devices).

Reverse-engineered from the official BlitzWolf Clean Android app — no cloud relay, no third-party dependencies. Communicates directly with the Slamtec IoT platform via OAuth2 + MQTT.

---

## Quick Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Sergioloid&repository=blitzwolf-clean-ha&category=integration)

Or manually add as a HACS custom repository (see below).

---

## Features

- **Real-time status** via MQTT push (no polling)
- **Full vacuum control**: start, stop, pause, return to dock
- **Fan speed modes**: Normal, Silence, High, Full
- **Battery level** with charging state
- **Extra attributes**: robot position, board temperature, WiFi info, sweep/mop mode, cleaning time
- **Config Flow UI**: set up from the HA interface, no YAML needed
- **HACS compatible**

## Supported Devices

| Brand | Model | Platform |
|-------|-------|----------|
| BlitzWolf | BW-VC1 | Slamtec SLAMWARE |
| Lambot | (various) | Slamtec SLAMWARE |

Other Slamtec-based robot vacuums using the same cloud (`cloud.slamtec.com`) may also work.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** > **...** (top right) > **Custom repositories**
3. Add this repository URL with category **Integration**
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/blitzwolf_vacuum/` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **BlitzWolf Vacuum**
3. Enter the email and password you use in the BlitzWolf Clean app
4. The integration will discover your robot and set it up automatically

## Entity

The integration creates a `vacuum` entity with:

| Feature | Details |
|---------|---------|
| **States** | `idle`, `cleaning`, `paused`, `docked`, `returning`, `error` |
| **Services** | `vacuum.start`, `vacuum.stop`, `vacuum.pause`, `vacuum.return_to_base`, `vacuum.set_fan_speed` |
| **Fan Speeds** | Normal, Silence, High, Full |
| **Battery** | Percentage + charging indicator |

### Extra Attributes

| Attribute | Description |
|-----------|-------------|
| `position_x` / `position_y` | Robot position on the map |
| `yaw` | Robot orientation |
| `temperature` | Internal board temperature |
| `sweep_time_seconds` | Current cleaning session duration |
| `device_mode` | `sweep` or `mop` |
| `wifi_ssid` / `wifi_ip` | Connected network info |
| `mqtt_connected` | MQTT connection status |

## Architecture

```
BlitzWolf Clean App (Android)
         |
         | (reverse-engineered)
         v
+------------------+       +----------------------+
|  OAuth2 REST API |       |     MQTT Broker      |
| cloud.slamtec.com| ----> | iot.slamtec.com:8883 |
+------------------+       +----------------------+
         |                           |
    authenticate              commands & status
    get devices              (JSON, function codes)
         |                           |
         v                           v
+------------------------------------------------+
|        Home Assistant Custom Integration        |
|                                                 |
|  api.py          -> OAuth2 + token refresh      |
|  coordinator.py  -> MQTT connection + state     |
|  vacuum.py       -> HA vacuum entity            |
|  config_flow.py  -> UI setup                    |
+------------------------------------------------+
```

### MQTT Protocol

Commands are JSON messages on topic `device/{device_id}/robot`:

```json
{"f": 24, "p": 1}     // Start cleaning
{"f": 24, "p": 2}     // Pause
{"f": 35}              // Stop
{"f": 36}              // Return to dock
{"f": 59, "p": 0}     // Set mode: 0=Normal, 1=Silence, 2=High, 3=Full
```

Status is received on topic `device/{device_id}/app`:

```json
{"f": 3, "p": 85}           // Battery: 85%
{"f": 4, "p": true}         // Charging: true
{"f": 1, "p": {"x": 1.2, "y": 3.4, "yaw": 0.5}}  // Position
{"f": 2, "p": {"an": 1}}    // Action: 1=sweeping
```

## Troubleshooting

- **"Cannot connect"**: Check that your BlitzWolf Clean app credentials are correct
- **Entity unavailable**: The MQTT connection may have dropped. Reload the integration
- **Token expired**: The integration auto-refreshes OAuth2 tokens. If issues persist, remove and re-add the integration

## Credits

Built by reverse-engineering the BlitzWolf Clean v1.2.2 Android APK (Slamtec `com.slamtec.android.robohome` platform).

## License

MIT
