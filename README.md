# GPTforHA (ChatGPT Plus HA)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)

GPTforHA is a Home Assistant add-on plus integration that connects your ChatGPT Plus account to Home Assistant without an API key. It runs a local sidecar that automates the ChatGPT web UI, then exposes it to Home Assistant for chat, automations, and AI suggestions.

## Capabilities
- ChatGPT Plus access with no API key
- Sidebar chat panel inside Home Assistant
- Automation-ready services for message sending and new conversations
- Persistent sessions stored in `/config/chatgpt_sessions`
- Guided login flow with a built-in VNC viewer (for headless=false)
- AI Task entity so it can appear in Assist > AI suggestions
- Ingress Web UI with health, status, login controls, and session reset

## How it works
- Add-on: runs the sidecar service and Playwright browser automation
- Integration: connects Home Assistant to the sidecar API
- Panel: a built-in chat UI in the HA sidebar

## Getting started

### Step 1: Install the add-on (backend)
1. Settings > Add-ons > Add-on Store.
2. Repositories > add: `https://github.com/jshafferman28/GPTforHA`
3. Install "ChatGPT Plus HA" and start it.
4. Enable Start on boot and Watchdog.

Docs: https://www.home-assistant.io/docs/add-ons/

### Step 2: First-time login
1. Add-on config: set `headless: false`.
2. Save and restart the add-on.
3. Open the add-on Web UI.
4. Click **Start login**, then **Open login viewer**.
5. Complete login in the viewer.
6. Click **Complete login**.
7. If needed, click **Clear session** and retry.
8. Set `headless: true`, save, restart.

### Step 3: Install the integration (frontend)
1. HACS > Integrations > Add Custom Repository:
   `https://github.com/jshafferman28/GPTforHA`
2. Install "ChatGPT Plus HA".
3. Restart Home Assistant.
4. Settings > Devices & Services > Add Integration > "ChatGPT Plus HA".
5. Use the default sidecar URL (`http://chatgpt_plus_ha:3000`).

Docs: https://hacs.xyz/docs/user/categories/ and https://www.home-assistant.io/docs/configuration/

## Usage
- Sidebar: open **ChatGPT** to chat in Home Assistant.
- Services: use `chatgpt_plus_ha.send_message` and `chatgpt_plus_ha.new_conversation`.
- AI Suggestions: Settings > Assist > AI suggestions, select **ChatGPT Plus AI Tasks**.

Docs: https://www.home-assistant.io/docs/assist/ and https://www.home-assistant.io/docs/automation/service-calls/

## Configuration
```
headless: true
```

## Troubleshooting
- Login fails: set `headless: false`, restart, use the login viewer, then **Complete login**.
- Blank viewer or errors: open add-on logs and verify the add-on is running.
- Stuck session: click **Clear session** or delete `/config/chatgpt_sessions/browser-state.json`.

## Notes
- This project automates the ChatGPT web UI, so selectors may change over time.
- Requires a ChatGPT Plus subscription and Home Assistant OS or Supervised.

## Updates
- Add-on: refresh the Add-on Store and click **Update**.
- Integration: update via HACS, then restart Home Assistant.

## Support
Issues: https://github.com/jshafferman28/GPTforHA/issues
