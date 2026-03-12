<p align="center">
  <img src="brand/icon.png" width="256" height="256" alt="SwitchBot API icon" />
</p>

# SwitchBot API for Home Assistant

A Home Assistant custom integration that provides direct access to the SwitchBot Cloud API. Control **all** your SwitchBot devices—including infrared remotes and devices not supported by the official SwitchBot Cloud integration—via services and REST commands.

## What It Does

This integration connects Home Assistant to the [SwitchBot Open API](https://github.com/OpenWonderLabs/SwitchBotAPI) using your token and secret from the SwitchBot app. It provides:

- **Device discovery** – Fetch and view all devices in your SwitchBot account with their IDs
- **Device control** – Send commands to any device via Home Assistant services or REST
- **Full API access** – Use the same API that powers the SwitchBot app, including infrared remotes and 50+ device types

## Why It Exists

The official [SwitchBot Cloud integration](https://www.home-assistant.io/integrations/switchbot_cloud/) only supports a limited set of device types. Many SwitchBot products—including infrared remotes (IR remotes), some smart plugs, and newer devices—are not exposed as entities in the official integration.

This integration gives you **direct API access**, so you can:

- Control infrared remotes (TVs, air conditioners, set-top boxes, etc.)
- Use devices not yet supported by the official integration
- Build automations with any SwitchBot device via services or REST
- Access the full SwitchBot API without waiting for official support

## How It Works

1. **Authentication** – You provide your SwitchBot Open API token and secret (from the SwitchBot app’s Developer Options). The integration uses HMAC-SHA256 signing for each request.
2. **Device list** – The integration fetches your devices from `GET /v1.1/devices`, including both physical devices (Bots, Curtains, Plugs, etc.) and infrared remotes.
3. **Commands** – Commands are sent via `POST /v1.1/devices/{deviceId}/commands` with the command, parameter, and command type you specify.

The integration also exposes:

- a diagnostic sensor with the most recent auth headers for inspection/debugging
- a `switchbot_api.get_auth_headers` service that returns a fresh header set on demand

---

## Installation

### Option 1: Manual Installation (custom_components)

1. **Download the integration**  
   - Download the [latest release zip](#releases) or clone this repository.

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

To control a device, you need its **device ID**. The integration provides several ways to get it:

### 1. Integration Options (easiest)

1. Go to **Settings → Devices & Services**
2. Find **SwitchBot API** and click **Configure**
3. The options screen shows a list of all devices with:
   - Device name  
   - Device type  
   - **Device ID** (e.g. `C271111EC0AB`)

### 2. `switchbot_api.get_devices` Service

Call the service to fetch the device list programmatically:

```yaml
service: switchbot_api.get_devices
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
      "device_type": "Infrared remote"
    }
  ],
  "device_count": 2,
  "physical_device_count": 1,
  "infrared_remote_count": 1
}
```

Use the `device_id` from this list when sending commands.

---

## Controlling Devices

### Using the Service

Use the `switchbot_api.send_command` service:

| Parameter      | Required | Default   | Description                                                                 |
|----------------|----------|-----------|-----------------------------------------------------------------------------|
| `device_id`    | Yes      | —         | The SwitchBot device ID (e.g. `C271111EC0AB`)                              |
| `command`      | No       | `turnOn`  | The command to send                                                         |
| `parameter`    | No       | `default` | Command parameter (string or object)                                        |
| `command_type` | No       | `command` | Usually `command`; use `customize` for infrared remotes with custom keys   |

#### Examples

**Turn on a Bot or Plug:**
```yaml
service: switchbot_api.send_command
data:
  device_id: "C271111EC0AB"
  command: "turnOn"
```

**Turn off:**
```yaml
service: switchbot_api.send_command
data:
  device_id: "C271111EC0AB"
  command: "turnOff"
```

**Press (Bot only – momentary press):**
```yaml
service: switchbot_api.send_command
data:
  device_id: "C271111EC0AB"
  command: "press"
```

**Set curtain position (0–100):**
```yaml
service: switchbot_api.send_command
data:
  device_id: "YOUR_CURTAIN_DEVICE_ID"
  command: "setPosition"
  parameter: "50"
```

**Infrared remote – power on TV:**
```yaml
service: switchbot_api.send_command
data:
  device_id: "02-202312011234-00"
  command: "turnOn"
  parameter: "default"
```

**Infrared remote – custom key:**
```yaml
service: switchbot_api.send_command
data:
  device_id: "02-202312011234-00"
  command: "customize"
  parameter: "your_custom_key_name"
  command_type: "customize"
```

### Using REST Commands

You can also control devices via REST using Home Assistant’s [RESTful Command](https://www.home-assistant.io/integrations/rest_command/) or [REST sensor/switch](https://www.home-assistant.io/integrations/rest/) integrations. The SwitchBot API requires signed headers.

The integration exposes a diagnostic sensor with the current auth headers (by default, an entity like `sensor.switchbot_api_auth_headers` unless you renamed it in the entity registry). It also exposes `switchbot_api.get_auth_headers`, which returns a fresh set of headers every time you call it.

#### Example: REST Command in `configuration.yaml`

```yaml
rest_command:
  switchbot_turn_on:
    url: "https://api.switch-bot.com/v1.1/devices/{{ device_id }}/commands"
    method: POST
    headers:
      Authorization: "{{ state_attr('sensor.switchbot_api_auth_headers', 'authorization') }}"
      t: "{{ state_attr('sensor.switchbot_api_auth_headers', 't') }}"
      nonce: "{{ state_attr('sensor.switchbot_api_auth_headers', 'nonce') }}"
      sign: "{{ state_attr('sensor.switchbot_api_auth_headers', 'sign') }}"
      Content-Type: "application/json"
    payload: '{"command":"turnOn","parameter":"default","commandType":"command"}'
    content_type: "application/json"
```

Call it with `device_id` in the service data, e.g.:
```yaml
service: rest_command.switchbot_turn_on
data:
  device_id: "C271111EC0AB"
```

**Note:** Replace `sensor.switchbot_api_auth_headers` with your actual entity ID. The sensor is diagnostic only and may still be stale for automation-heavy use. For reliable command execution, use `switchbot_api.send_command`, which signs each request at send time.

If you need raw auth values outside this integration, call `switchbot_api.get_auth_headers` and use the returned `authorization`, `t`, `nonce`, `sign`, `generated_at`, and `expires_at` values immediately.

Example in an automation/script using a response variable:

```yaml
- action: switchbot_api.get_auth_headers
  response_variable: switchbot_auth

- action: rest_command.some_external_switchbot_call
  data:
    authorization: "{{ switchbot_auth['authorization'] }}"
    t: "{{ switchbot_auth['t'] }}"
    nonce: "{{ switchbot_auth['nonce'] }}"
    sign: "{{ switchbot_auth['sign'] }}"
```

#### Simpler approach: Call the service from REST

Expose the `switchbot_api.send_command` service via the [Home Assistant REST API](https://www.home-assistant.io/api/rest/) and call it from external systems:

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_HA_LONG_LIVED_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"C271111EC0AB","command":"turnOn"}' \
  https://your-ha-instance:8123/api/services/switchbot_api/send_command
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
| Curtain     | `setPosition` | `0`–`100` | Set position (percent)   |
| Lock        | `lock`      | `default`   | Lock                     |
| Lock        | `unlock`    | `default`   | Unlock                   |
| IR Remote   | `turnOn`    | `default`   | Depends on remote setup  |
| IR Remote   | `turnOff`   | `default`   | Depends on remote setup  |
| IR Remote   | `customize` | key name    | `command_type: customize`|

For full details, see the [SwitchBot Open API documentation](https://github.com/OpenWonderLabs/SwitchBotAPI).

---

## Releases and Download

### Download as ZIP

1. Go to the [Releases](https://github.com/JGKarlin/switchbot_api/releases) page
2. Download the latest `switchbot_api.zip`
3. Extract the `switchbot_api` folder
4. Copy it to `config/custom_components/switchbot_api/`

### Creating a Release ZIP

A script is included to build the zip. From the repository root:

```bash
chmod +x create_release_zip.sh
./create_release_zip.sh
```

This creates `switchbot_api.zip` containing the correctly named `switchbot_api` folder for `custom_components`. You can attach this zip to a GitHub release for easy downloads.

---

## Requirements

- Home Assistant 2024.x or later (or compatible version)
- SwitchBot account with Open API token and secret
- Internet access (API is cloud-based)

---

## Troubleshooting

- **Invalid token or secret** – Regenerate your token in the SwitchBot app and re-enter it in the integration.
- **Device not responding** – Confirm the device is online in the SwitchBot app and that you’re using the correct `device_id`.
- **Command not working** – Check the [SwitchBot API docs](https://github.com/OpenWonderLabs/SwitchBotAPI) for your device type and supported commands.
- **REST auth fails** – Auth headers expire quickly. Use `switchbot_api.send_command` when possible, or fetch a fresh set with `switchbot_api.get_auth_headers` immediately before making the external request.

---

## Publishing to GitHub

1. Create a new public repository on GitHub (e.g. `switchbot_api`)
2. (Optional) Update the Releases URL in this README if you fork the repo
3. Add repository description and topics: `home-assistant`, `switchbot`, `custom-integration`, `iot`
4. Push your code and create a release:
   - Run `./create_release_zip.sh` to generate `switchbot_api.zip`
   - Create a new release, tag it (e.g. `v2.2.1`), and attach `switchbot_api.zip` as an asset
5. For HACS: Users can add your repo as a custom repository (HACS → Integrations → ⋮ → Custom repositories) with `content_in_root: true`

---

## License

MIT License (or your preferred license)
