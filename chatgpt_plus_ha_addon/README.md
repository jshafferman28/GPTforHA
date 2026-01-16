# ChatGPT Plus HA Add-on

This add-on runs a local sidecar service that automates the ChatGPT web UI using your ChatGPT Plus subscription.

## Getting started
1. Install the add-on from the Add-on Store and start it.
2. Open the add-on Web UI to view status.
3. For first-time login, set `headless: false`, save, and restart the add-on.
4. Open the Web UI and click **Start login** (or visit `/api/login`) to launch the login page.
5. Complete login, then click **Complete login** (or call `/api/login/complete`).
6. Set `headless: true`, save, and restart.

## Configuration
```
headless: true
```

## Notes
- Sessions are stored in `/config/chatgpt_sessions`.
- Headed login uses Xvfb inside the add-on, so no external display is needed.
- The add-on also adds a sidebar panel entry named "ChatGPT Plus".

## Updates
- Open the Add-on Store, refresh, and click **Update** when a new version is available.
- No uninstall/reinstall is needed as long as the version is bumped.
