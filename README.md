<p align="center">
  <img src="brand/icon.png" width="256" height="256" alt="SwitchBot API icon" />
</p>

# SwitchBot API for Home Assistant

A Home Assistant custom integration that provides direct access to the SwitchBot Cloud API. Control **all** your SwitchBot devices—including infrared remotes and devices not supported by the official SwitchBot Cloud integration—via a single service action.

## What It Does

This integration connects Home Assistant to the [SwitchBot Open API](https://github.com/OpenWonderLabs/SwitchBotAPI) using your token and secret from the SwitchBot app. It provides:

- **Device discovery** – Fetch and view all devices in your SwitchBot account with a device name dropdown
- **Device control** – Send commands to any device via `switchbot_api.send_command` with automatic command type detection
- **Full API access** – Use the same API that powers the SwitchBot app, including infrared remotes and 50+ device types
- **API status monitoring** – Validates your credentials every 10 minutes and shows `connected`, `authentication_failed`, or `connection_error`
- **Credential management** – Update your token and secret via Reconfigure without removing the integration

## Why It Exists

The official [SwitchBot Cloud integration](https://www.home-assistant.io/integrations/switchbot_cloud/) only supports a limited set of device types. Many SwitchBot products—including infrared remotes (IR remotes), some smart plugs, and newer devices—are not exposed as entities in the official integration.

This integration gives you **direct API access**, so you can:

- Control infrared remotes (TVs, air conditioners, set-top boxes, etc.)
- Use devices not yet supported by the official integration
- Build automations with any SwitchBot device
- Access the full SwitchBot API without waiting for official support

## How It Works

1. **Authentication** – You provide your SwitchBot Open API token and secret (from the SwitchBot app's Developer Options). The integration uses HMAC-SHA256 signing for each request.
2. **Device list** – The integration fetches your devices from `GET /v1.1/devices` on startup and caches them. Both physical devices and infrared remotes are included.
3. **Device selection** – When using `switchbot_api.send_command`, select your device by name from a dropdown. The device ID, type, and command type are resolved automatically.
4. **Commands** – Commands are sent via `POST /v1.1/devices/{deviceId}/commands`. For most commands, the parameter defaults to `default` and the command type is auto-detected based on the device type.

---

## Installation

### Option 1: Manual Installation (custom_components)

1. **Download the integration**
   - Download the [latest release zip](https://github.com/JGKarlin/switchbot_api/releases) or clone this repository.

2. **Install in Home Assistant**
   - Copy the `switchbot_api` folder into your Home Assistant `custom_components` directory:
     ```
     config/custom_components/switchbot_api/
     ```
   - The folder name **must** be `switchbot_api` (matching the integration domain).

3. **Restart Home Assistant**
   - Restart Home Assistant so it loads the new integration.

4. **Configure**
   - Go to **Settings → Devices & Services → Add Integration**
   - Search for **SwitchBot API** and add it
   - Enter your token and secret from the SwitchBot app

### Option 2: HACS (Custom Repository)

1. Open **HACS → Integrations**
2. Click the **⋮** menu (top right) → **Custom repositories**
3. Add this repository URL and select **Integration**
4. Search for **SwitchBot API** and install
5. Restart Home Assistant and add the integration via **Settings → Devices & Services**

### Getting Your Token and Secret

1. Open the SwitchBot app
2. Go to **Profile → Preferences** (or **Preferences → About** on app 9.0+)
3. Tap the **App Version** number 10 times to reveal Developer Options
4. Tap **Developer Options**, then **Get Token**
5. Copy your **token** and **secret** and enter them in the integration setup

---

## Device List and IDs

To see your devices and their IDs:

### 1. Refresh Button (on the device page)

The **Refresh device list** button on the SwitchBot API device page fetches the latest device list from the API. Click into the button entity to see all devices in the attributes panel, grouped by physical devices and infrared remotes, with names, types, and IDs.

### 2. Integration Options

1. Go to **Settings → Devices & Services**
2. Find **SwitchBot API** and click **Configure**
3. The options screen shows all devices grouped by type with their IDs

### 3. `switchbot_api.get_devices` Service

Call the service to fetch the device list programmatically:

```yaml
action: switchbot_api.get_devices
```

The response includes:

```json
{
  "devices": [
    {
      "device_id": "C271111EC0AB",
      "device_name": "Living Room Bot",
      "device_type": "Bot"
    },
    {
      "device_id": "02-202312011234-00",
      "device_name": "TV Remote",
      "device_type": "Others"
    }
  ],
  "device_count": 2,
  "physical_device_count": 1,
  "infrared_remote_count": 1
}
```

---

## Controlling Devices

### Using the Service

Use `switchbot_api.send_command` to control any device:

| Parameter      | Required | Default   | Description                                                                 |
|----------------|----------|-----------|-----------------------------------------------------------------------------|
| `device_name`  | No*      | —         | Select from the dropdown (e.g. `Door [Smart Lock]`)                        |
| `device_id`    | No*      | —         | Raw device ID for YAML automations (e.g. `C271111EC0AB`)                   |
| `command`      | No       | `turnOn`  | The command to send                                                         |
| `parameter`    | No       | `default` | Command parameter (string or JSON object)                                   |
| `command_type` | No       | auto      | Auto-detected: `command` for physical devices, `customize` for IR "Others" |

*Either `device_name` or `device_id` must be provided.

The `command_type` is automatically determined based on the device type — you typically don't need to set it.

### Examples

**Turn on a Bot or Plug (using device name from dropdown):**
```yaml
action: switchbot_api.send_command
data:
  device_name: "Plug Mini [Plug Mini (JP)]"
  command: "turnOn"
```

**Lock a Smart Lock (using device ID):**
```yaml
action: switchbot_api.send_command
data:
  device_id: "C77BA846E246"
  command: "lock"
```

**Set curtain position:**
```yaml
action: switchbot_api.send_command
data:
  device_id: "E3D02BF388C7"
  command: "setPosition"
  parameter: "0,ff,50"
```

**Set AC temperature (IR Air Conditioner):**
```yaml
action: switchbot_api.send_command
data:
  device_id: "02-202406031344-38077653"
  command: "setAll"
  parameter: "26,2,3,on"
```

**Infrared remote – custom button (IR "Others"):**
```yaml
action: switchbot_api.send_command
data:
  device_id: "03-202603050254-93377662"
  command: "Power"
  command_type: "customize"
```

### Using in Automations

```yaml
automation:
  - alias: "Lock door at night"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - action: switchbot_api.send_command
        data:
          device_id: "C77BA846E246"
          command: "lock"
```

---

## Common Commands by Device Type

| Device Type | Command     | Parameter   | Notes                    |
|-------------|-------------|-------------|--------------------------|
| Bot, Plug   | `turnOn`    | `default`   | Turn on                  |
| Bot, Plug   | `turnOff`   | `default`   | Turn off                 |
| Bot         | `press`     | `default`   | Momentary press          |
| Curtain     | `turnOn`    | `default`   | Open                     |
| Curtain     | `turnOff`   | `default`   | Close                    |
| Curtain     | `setPosition` | `0,ff,50` | index,mode,position      |
| Lock        | `lock`      | `default`   | Lock                     |
| Lock        | `unlock`    | `default`   | Unlock                   |
| IR AC       | `setAll`    | `26,2,3,on` | temp,mode,fan,power      |
| IR Remote   | `turnOn`    | `default`   | Turn on (standard)       |
| IR Others   | (button name) | `default` | `command_type: customize`|

For the full command reference for all 50+ device types, see the [SwitchBot Open API documentation](https://github.com/OpenWonderLabs/SwitchBotAPI).

---

## Entities

The integration creates the following entities on the **SwitchBot API** device:

| Entity | Category | Description |
|--------|----------|-------------|
| **API status** | Diagnostic | Shows `connected`, `authentication_failed`, or `connection_error`. Validates credentials every 10 minutes. Auth headers are available in the entity attributes. |
| **Refresh device list** | Configuration | Press to refresh the cached device list from the API. The full device list is visible in the entity's attributes. |

---

## Updating Credentials

If your SwitchBot token or secret changes:

1. Go to **Settings → Devices & Services**
2. Find **SwitchBot API**, click the **⋮** menu
3. Select **Reconfigure**
4. Enter your new token and secret
5. The integration validates the new credentials and reloads automatically

The **API status** sensor will show `authentication_failed` within 10 minutes if credentials become invalid.

---

## Releases and Download

### Download as ZIP

1. Go to the [Releases](https://github.com/JGKarlin/switchbot_api/releases) page
2. Download the latest `switchbot_api.zip`
3. Extract the `switchbot_api` folder
4. Copy it to `config/custom_components/switchbot_api/`

---

## Requirements

- Home Assistant 2024.1.0 or later
- SwitchBot account with Open API token and secret
- Internet access (API is cloud-based)

---

## Troubleshooting

- **Invalid token or secret** – Regenerate your token in the SwitchBot app. Use **Reconfigure** (⋮ menu on the integration card) to update credentials without removing the integration.
- **Device not responding** – Confirm the device is online in the SwitchBot app and that you're using the correct `device_id`.
- **Command not working** – Check the [SwitchBot API docs](https://github.com/OpenWonderLabs/SwitchBotAPI) for your device type and supported commands.
- **Device dropdown is empty** – Press the **Refresh device list** button on the device page, then reload the integration.
- **API status shows `authentication_failed`** – Your token or secret has changed. Use Reconfigure to update them.
- **API status shows `connection_error`** – Check your internet connection. The SwitchBot API is cloud-based and requires internet access.

---

## License

MIT License (or your preferred license)
