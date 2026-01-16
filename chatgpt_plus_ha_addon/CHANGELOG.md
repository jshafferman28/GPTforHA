# Changelog

## 1.1.6
- Improve response detection to avoid timeouts on completed replies.

## 1.1.5
- Fix ingress path handling for VNC assets and WebSocket.
- Add VNC connection logging and resilient noVNC loader.

## 1.1.4
- Fix VNC WebSocket protocol under ingress.

## 1.1.3
- Fix ingress VNC module path and WebSocket endpoint.

## 1.1.2
- Fix Web UI template parsing error in the VNC viewer.

## 1.1.1
- Serve noVNC locally to fix blank login viewer.
- Add clear session endpoint and Web UI button.

## 1.1.0
- Add VNC login viewer for headless=false authentication.

## 1.0.9
- Fix ingress Web UI links and JSON parsing.
- Add sidebar panel entry in Home Assistant.

## 1.0.8
- Replace xvfb-run with direct Xvfb startup.
- Add Web UI buttons for login and login completion.

## 1.0.7
- Run headed browser via Xvfb when headless is disabled.

## 1.0.6
- Add AI Task entity so ChatGPT appears in AI suggestions.

## 1.0.5
- Improve login detection using ChatGPT session API.
- Show headless status and login instructions in the Web UI.

## 1.0.4
- Use system Chromium if Playwright browsers are missing.
- Add a root status page for ingress Web UI.

## 1.0.3
- Fix add-on start script location and permissions.
- Add add-on README and changelog for the store.

## 1.0.2
- Ensure Playwright install uses environment flags.

## 1.0.1
- Add ingress support and response matching.
