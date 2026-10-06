# MAYA Browser Bridge

This unpacked Chrome extension connects MAYA Core to the user's already signed-in
Gmail, WhatsApp Web, and Telegram Web sessions. It does not store passwords or copy
browser cookies.

## One-time installation

Before loading the extension, pin the Chrome profile MAYA should treat as **main**:

```powershell
cd D:\MAYA
python scripts/configure_chrome_main_profile.py
```

Choose the profile from the local list. MAYA stores only the selected Chrome profile
directory under `%LOCALAPPDATA%\Maya\settings.json`.

Then install the extension:

1. Start MAYA Core with `python maya_server.py`.
2. Open the **same Chrome profile** MAYA should use for communication.
3. Visit `chrome://extensions`.
4. Enable **Developer mode**.
5. Choose **Load unpacked**.
6. Select this folder: `apps/chrome-extension`.
7. Keep the extension enabled.

The manifest contains a fixed public extension key so its extension ID is stable:
`cbffklcgjeagclgldpkiflcbgbmjgohh`.

MAYA Core only allows the local UI and that exact extension origin to access the
local bridge.

## Safety model

- Preparing/drafting a message: Level 2 safe action.
- Actually sending external communication: Level 3 modification action.
- With the default MAYA permission level (2), Send requires a one-time confirmation
  bound to the exact recipient, service and message arguments.
- Ambiguous recipient matches fail instead of guessing.
- Gmail currently requires an exact email address.
- Text messages are implemented first. Local file/screenshot attachments are
  intentionally reported as unsupported until verified attachment handoff is added.

## Supported services

- Gmail: compose, fill recipient/subject/body, send, verify "Message sent".
- WhatsApp Web: exact contact lookup, compose, send, verify composer cleared.
- Telegram Web: exact contact lookup, compose, send, verify composer cleared.

Web applications change their DOM over time, so adapters are defensive and return a
real failure instead of claiming success when expected UI elements are not found.
