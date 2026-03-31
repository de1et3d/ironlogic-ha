# IronLogic IP Controller for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/de1et3d/ironlogic-ha)
![GitHub](https://img.shields.io/github/license/de1et3d/ironlogic-ha)

> 🇷🇺 [Документация на русском](./README_ru.md)

> ⚠️ **DISCLAIMER:** This is an **unofficial community integration**. The author is **not affiliated with IronLogic** in any way. IronLogic and its logo are trademarks of IronLogic. This project does not intend to infringe on any rights, and the author would be happy to see an official integration released by the company. This integration was written using AI tools. Use at your own risk.

## 📌 Features

- Remote lock control - open via HA (instant HTTP API + queued Web-JSON fallback)
- Real‑time events - track key grants/denials, door open/close, network commands
- Key management - add/remove/export/import keys directly from HA
- Door sensor support - binary sensor for door position (requires magnetic contact)
- Controller availability monitoring - all entities become unavailable when controller is offline
- Controller reboot - reboot the controller directly from HA
- Local & offline‑friendly - controller works autonomously even when HA is down
- Multi‑controller - add multiple IronLogic devices
- Device controls - enable/disable door sensor and adjust poll interval directly on the device page
- Translations - English and Russian

## 🧪 Tested Environment

This integration has been tested with:

| Component | Version |
| :--- | :--- |
| **Controller** | IronLogic Z-5R (mod. Wi-Fi) |
| **Controller FW** | 2.55 |
| **Wi-Fi Module FW** | 1.79 |
| **Web-JSON Mode** | HTTP (not Websocket) |
| **Home Assistant** | Core 2026.3.3, 2026.3.4 (HA OS) |
| **Supervisor** | 2026.03.2 |
| **Operating System** | 17.1 |
| **Frontend** | 20260312.0 |

**Important notes:**
- HTTPS may work unreliably or not work at all. Use HTTP for controller communication.
- If you need HTTPS for HA while keeping HTTP for the controller, use a reverse proxy (e.g., Nginx Proxy Manager add-on).
- Controller and HA should be in the same subnet. Cross-subnet operation was not tested.
- Domain names can be used if the controller can access DNS.

## 🏗️ Supported IP controllers

- Z-5R (Wi‑Fi) - *tested*
- Z-5R (Web)
- Z-5R (Web BT)
- Matrix-II (EH K Wi‑Fi)
- Any IronLogic controller with Web-JSON protocol support

## 🔧 Hardware Requirements

- IronLogic IP Controller
- NFC/RFID reader (e.g., Matrix‑III NFC)
- Electric lock (electromechanical or electromagnetic)
- 12V power supply
- Optional: magnetic contact sensor for door status

## 📦 Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations → Custom repositories**
3. Add repository URL: `https://github.com/de1et3d/ironlogic-ha`
4. Select category: **Integration**
5. Click **Download** and restart HA

### Manual installation

1. Download the latest release
2. Copy `custom_components/ironlogic` to `config/custom_components/`
3. Restart Home Assistant

## ⚙️ Configuration

### Step-by-step setup

1. **Add the integration**
   - Go to **Settings → Devices & Services → Add Integration**
   - Search for **"IronLogic IP Controller"**
   - Choose setup method:
     - **Scan network for controllers** — automatically scans the local /24 subnet (up to 254 IP addresses) for IronLogic controllers
     - **Configure manually** — enter the IP address manually

2. **If scanning is selected:**
   - Wait for the scan to complete (up to 30 seconds)
   - Select your controller from the list
   - Enter the **Username** and **Authentication key**

3. **If manual configuration is selected:**
   - Enter:
     - **Host** — IP address of your controller (e.g., `192.168.1.100`)
     - **Username** — depends on model: Z-5R (Wi-Fi): `z5rwifi`, Z-5R Web: `z5rweb`, Matrix-II (Wi-Fi): `matrix`
     - **Auth Key** — 8‑character key from the controller. If you changed it from the factory default, find it in the controller's web interface under "Work Mode" settings.

4. **Configure webhook**
   - On the device page, click the **"Set webhook URL"** button.
   - Then click **"Reboot controller"** to apply the settings.
   - The controller will start sending events to Home Assistant.

   *Alternatively, you can find the webhook URL in the **Webhook URL** sensor under Diagnostics if you need to configure it manually. Click on it → open the detail card → three dots → details → copy the `full_url` attribute.*

5. **Verify**
   - After reboot, the controller should send `power_on` to HA.
   - The device name will update to `IronLogic (SN @ IP)` once the serial number is received.
   - If nothing happens, check network connectivity and logs.

> ⚠️ **Important:** The controller must be able to reach your Home Assistant instance. Use a local IP if both are on the same network.

### Debug server (for troubleshooting)

If you need to debug the Web-JSON communication, you can use the included debug server.
See [debug_server.py](debug_server.py) for a simple Python script that logs all controller requests.

## 🎮 Entities Created

| Entity | Type | Purpose |
|---|---|---|
| `lock.door_lock` | Lock | Momentary door opening |
| `binary_sensor.door` | Binary sensor | Door open/closed status (optional, enabled via switch) |
| `binary_sensor.controller_availability` | Binary sensor | Controller connectivity status |
| `sensor.last_event` | Sensor | Last event description (e.g., "Key granted: John", "Door closed") |
| `sensor.last_key` | Sensor | Last key used with status (e.g., "12345678 (granted)", "87654321 (denied)") |
| `sensor.serial_number` | Sensor | Controller serial number (automatically detected) |
| `sensor.webhook_url` | Sensor | Webhook path (with `full_url` attribute) |
| `switch.door_sensor` | Switch | Enable/disable door sensor (in device Controls) |
| `number.poll_interval` | Number | Controller availability check interval (in device Controls) |
| `button.reboot` | Button | Reboot the controller (in device Diagnostics) |
| `button.set_webhook` | Button | Automatically configure webhook URL in controller |

## 🔑 Key Management (in development)

| Service | Description |
|---|---|
| `ironlogic.add_key` | Add a new key |
| `ironlogic.remove_key` | Remove a key |
| `ironlogic.clear_all_keys` | Delete all keys |
| `ironlogic.export_keys` | Export keys to CSV |
| `ironlogic.import_keys` | Import keys from CSV |

*Note: Legacy service names (`add_card`, `remove_card`, `clear_all_cards`) are still available for compatibility.*

## 🎯 Events for Automations

| Event | Description |
|---|---|
| `ironlogic_key_granted` | Key accepted, door opened |
| `ironlogic_key_denied` | Key rejected |
| `ironlogic_door_opened` | Door opened (if door sensor enabled) |
| `ironlogic_door_closed` | Door closed (if door sensor enabled) |
| `ironlogic_door_tampered` | Door opened without authorization (tamper) |
| `ironlogic_door_left_open` | Door left open timeout |
| `ironlogic_door_opened_remotely` | Door opened via HA or network |

### Example Automation

```yaml
automation:
  - alias: "Notify when door opened with key"
    trigger:
      - platform: event
        event_type: ironlogic_key_granted
    action:
      - service: notify.mobile_app_phone
        data:
          message: "Door opened by {{ trigger.event.data.key_name or trigger.event.data.key }}"

  - alias: "Notify on unauthorized access"
    trigger:
      - platform: event
        event_type: ironlogic_key_denied
    action:
      - service: notify.mobile_app_phone
        data:
          message: "Unauthorized access attempt with key {{ trigger.event.data.key }}"
```

## 🧠 How It Works

- **Web‑JSON** - controller sends POST requests to HA webhook; HA responds with commands
- **HTTP API** - HA can instantly open the door without waiting for the next controller ping
- **Availability monitoring** - HA periodically checks controller connectivity; all entities become unavailable if controller is offline
- **Device controls** - door sensor and poll interval can be configured directly on the device page
- Commands are queued if the controller is offline - delivered when connection resumes

## 📝 CSV Format for Import/Export

```csv
key_number,name,type,added_at,last_used
00B5009EC1A8,John's key,normal,2024-01-15 10:30:00,2026-01-16 08:20:00
000000BB076B,Guest key,blocking,2024-01-16 09:15:00,
```

## 🐛 Troubleshooting

### No events received

- Ensure controller mode is **Web‑JSON** with **HTTP** protocol
- Verify server URL is correct (try local IP, not domain)
- Check network connectivity between controller and HA
- Check Home Assistant logs for `custom_components.ironlogic`

### Authentication failed

- Verify username (case‑sensitive, depends on model)
- Check auth key (8 characters, case‑sensitive). If you changed it, find it in controller's web interface under "Work Mode" settings.
- Try logging into the controller web UI with the same credentials

### Door not opening

- Check wiring between controller and lock
- Verify lock type setting in controller web UI
- Try opening via controller web UI to isolate HA issues

### Door sensor not showing

- Ensure magnetic contact is connected to controller
- Enable door sensor via the switch in device Controls
- Door sensor events will only appear when the switch is ON

## 🚧 Planned Features

- Full key management with UI
- Controller settings synchronization (open time, passage timeout, etc.)
- Advanced key management (time zones, block lists)

## 🤝 Contributing

- Fork the repository
- Create a feature branch
- Submit a pull request

## 📄 License

Licensed under **Apache License 2.0**. See `LICENSE` file for details.
