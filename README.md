# ChatGPT Plus HA

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)

A Home Assistant Add-on and Integration that lets you chat with ChatGPT using your ChatGPT Plus subscription (no OpenAI API key required).

## Features
- Easy installation through the Home Assistant Add-on Store
- Sidebar chat panel
- Conversation memory
- Services for automations
- Persistent session after login

## Getting started

### Step 1: Install the Add-on (Backend)
1. Go to Settings > Add-ons > Add-on Store.
2. Open the menu (top right) and choose Repositories.
3. Add this URL: `https://github.com/jshafferman28/GPTforHA`
4. Find "ChatGPT Plus HA" and install it.
5. Start the add-on (enable Start on boot and Watchdog).

Docs: https://www.home-assistant.io/docs/add-ons/

### Step 2: First-Time Login
1. Open the add-on configuration.
2. Set `headless: false`.
3. Save and restart the add-on.
4. Open the add-on Web UI and visit `/api/login`.
5. Complete login, then call `/api/login/complete`.
6. Go back to configuration and set `headless: true`.
7. Save and restart.

Your session is saved in `/config/chatgpt_sessions`.

### Step 3: Install the Integration (Frontend)
1. Open HACS.
2. Add Custom Repository: `https://github.com/jshafferman28/GPTforHA` (Category: Integration).
3. Install "ChatGPT Plus HA".
4. Restart Home Assistant.
5. Go to Settings > Devices & Services > Add Integration.
6. Search for "ChatGPT Plus HA".
7. Use the default URL: `http://chatgpt_plus_ha:3000`.
8. Submit.

Docs: https://hacs.xyz/docs/user/categories/ and https://www.home-assistant.io/docs/configuration/

## Usage
Click "ChatGPT" in your sidebar to start chatting.

## AI Suggestions
This integration registers an AI Task entity so it can be selected under Settings > Assist > AI suggestions.
Choose "ChatGPT Plus AI Tasks" for data generation tasks.

Docs: https://www.home-assistant.io/docs/assist/

### Services
- `chatgpt_plus_ha.send_message`
- `chatgpt_plus_ha.new_conversation`

Docs: https://www.home-assistant.io/docs/automation/service-calls/

## Troubleshooting
Check the add-on logs for browser errors. If login fails, repeat the login steps with headless mode disabled.

## Updates
After pulling new versions of this repository, refresh the Add-on Store and click **Update** on the add-on. You should not need to uninstall as long as the version changes.
