# ChatGPT Plus HA Add-on

This add-on runs a local sidecar service that automates the ChatGPT web UI using your ChatGPT Plus subscription.

## Usage
- Open the add-on Web UI to view status and access login endpoints.
- Set `headless: false` to log in via the browser window, then switch back to `headless: true`.

## Configuration
```
headless: true
```

## Notes
- Sessions are stored in `/config/chatgpt_sessions`.

## Updates
- Open the Add-on Store, refresh, and click **Update** when a new version is available.
- No uninstall/reinstall is needed as long as the version is bumped.
