# v0.9.1 - Four-channel curves, Wi-Fi and starter presets

Vector ZC95 Live now supports four independently editable channel curves, with a live 2D overview and rotatable 3D ribbons. MFP-driven output works over Bluetooth or Wi-Fi; MFP input can use UDP, WebSocket or TCP.

- Smooth curves with draggable/editable points and reusable curve shapes.
- Per-channel power envelopes, damped pulse repetition/width, and optional Channel 1 texture following.
- Vector rolling-speed volume with a two-second look-ahead buffer.
- Wi-Fi output with corrected physical-dial scaling; the device Limit screen is expected.
- Stable connection controls and Bluetooth-only Scale confirmation.
- Optional native pattern player when no funscript is available, including device-supplied controls and Lua upload into empty slots.
- Steve's tested four-channel curves and settings included as the fresh-install starter preset.

Download the ZIP, extract it, and run START_VECTOR_ZC95.bat. Python 3.10+ and desktop Chrome/Edge are required; no pip dependencies. Existing users should close the old launcher and copy settings-zc95-v3.json into the new folder to retain their settings. New installs load starter-settings.json automatically.

The starter has all four channels enabled, with Channel 1/2 software maxima of 100%. Review the included background/maximum ranges and begin with physical dials at zero. The application starts stopped and requires an explicit Start or Play.

MFP-driven output, Wi-Fi dial scaling and basic native pattern playback have been tested on hardware by the project owner. Automated regression checks pass. The Lua player remains a basic optional feature; unsupported native audio/display widgets are not reproduced.
