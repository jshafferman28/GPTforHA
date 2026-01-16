# GPTforHA Sidecar Add-on

This add-on runs the local ChatGPT Plus sidecar for Home Assistant. It automates the ChatGPT web UI and exposes a simple API that the integration uses for chat and AI tasks.

## Capabilities
- Local sidecar API for ChatGPT Plus
- Ingress Web UI with login controls and status
- Built-in VNC login viewer (for headless=false)
- Persistent sessions stored in `/config/chatgpt_sessions`

## Getting started
1. Install the add-on from the Add-on Store and start it.
2. Open the add-on Web UI to confirm status.
3. For first-time login, set `headless: false`, save, and restart.
4. Click **Start login**, then **Open login viewer**.
5. Complete login, then click **Complete login**.
6. If login fails, click **Clear session** and retry.
7. Set `headless: true`, save, and restart.

## Configuration
```
headless: true
```

## Notes
- Headed login uses Xvfb inside the add-on. No external display needed.
- The integration uses this add-on as its backend and exposes the ChatGPT panel.

## Updates
- Open the Add-on Store, refresh, and click **Update** when a new version is available.
