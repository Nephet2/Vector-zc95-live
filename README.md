# Vector ZC95 Live

A standalone Windows controller that turns MultiFunPlayer T-code into dynamic ZC95 output over Bluetooth or Wi-Fi. Four numbered channels have independent editable curves, power envelopes, pulse repetition and pulse width. This is a separate application from ReStim Vector; ReStim and FOCSTIM are not required.

## Download and run

Download the ZIP from [Releases](https://github.com/Nephet2/Vector-zc95-live/releases), extract it, and run `START_VECTOR_ZC95.bat`. You need Python 3.10 or newer and desktop Chrome or Edge. No pip packages are required. Keep the launcher terminal open.

The interface opens at `http://127.0.0.1:8766`. Close an older Vector ZC95 launcher before starting a new one. Settings save automatically in `settings-zc95-v3.json` beside the launcher. When upgrading, copy your existing settings file into the new folder before launching.

## Included starter preset

Fresh installs load Steve's tested configuration from `starter-settings.json`. Existing saved settings take precedence. The starter includes four smooth curves on L0, Vector rolling-speed power, a two-second buffer, and damped frequency/width response.

| Channel | Background command | Maximum command | Pulse repetition | Width per phase |
| --- | ---: | ---: | ---: | ---: |
| 1 | 38.5% | 100% | 40-183 Hz | 80-120 us |
| 2 | 43% | 100% | 40-100 Hz | 80-120 us |
| 3 | 0% | 10% | 40-100 Hz | 80-120 us |
| 4 | 0% | 10% | 40-100 Hz | 80-120 us |

All four channels are enabled in this preset. These are software command percentages before the physical dial multiplier, not measured watts or calibrated sensation. Review the ranges and start with the device dials at zero. The app always starts with hardware output stopped; loading settings never starts output.

## MultiFunPlayer input

Configure one MFP output to Vector, then select the matching input transport in Vector:

| Transport | MFP destination |
| --- | --- |
| UDP | Host `127.0.0.1`, port `12355` |
| WebSocket | `ws://127.0.0.1:12355/ws` |
| TCP | Host `127.0.0.1`, port `12355`, newline-delimited T-code |

UDP works well locally and has no persistent connection to drop. Configure repeated output, including stationary positions, ideally every 100-500 ms. UDP input expires after the current T-code interval plus two seconds of silence. Healthy WebSocket/TCP connections support idle holds. Auto accepts all supported transports; use one MFP output at a time to avoid competing sources. Changing the input selection stops hardware and clears old input.

## Connect over Bluetooth

Put the ZC95 in BLE remote mode. Select Bluetooth, click Connect ZC95, and choose the device. Set Power dial mode to **Scale** on the ZC95 and tick the Bluetooth-only confirmation. Review your settings, supply live MFP input, then press Start output.

## Connect over Wi-Fi

Connect the ZC95 to your Wi-Fi through its Remote Access configuration. Select Wi-Fi in Vector and enter the IP shown on the device. Both PC and ZC95 must be on the same LAN. Close other device clients. Allow local-network access if Chrome asks.

For Vector/MFP output, the first connection installs `vector_wifi.lua` in an empty Lua slot. It never overwrites an existing script. The receiver is named **Vector WiFi v1** and is reused on later connections. If no empty slot is available, installation stops with an explanation.

Click Start output after connecting. Wi-Fi remote mode shows the device's **Limit** screen. Vector follows reported dial levels through remote power and Lua multiplies by the Vector command, providing the intended scaling: 20% Vector command with a 50% dial gives approximately 10% output on the firmware command scale. Feedback can take about 250 ms plus network time; dial reductions retain the firmware's immediate clamp.

Both output transports start with a two-second ramp and use the full configured range, without an extra test cap or timed-test duration. The browser watchdog pauses on a stalled command feed. The Wi-Fi receiver additionally zeros output if no committed frame arrives for 1.5 seconds while its Lua loop is running. A frozen device cannot execute that check.

Unexpected connection/source interruptions can pause and resume Vector output while Run remains requested, with a new ramp. Stop, Disconnect and Hard Neutral cancel that request. Keep the control tab visible; hiding it pauses output. Connection alone never starts output.

## Curves and dynamic response

The curve editor maps source position (X, 0-100%) to response (Y, 0-100%) independently for each channel. Drag points, double-click to add, or edit selected coordinates numerically. Endpoints stay at X=0 and X=100. Up to 24 points are supported. Smooth interpolation passes through points without overshooting neighbouring point values; linear interpolation is also available.

Built-in curve presets include flat, rising, falling, bell, valley and crossover shapes. Two-channel crossover and four-staggered-peak presets provide alternative layouts. These stop hardware before changing mappings. The 2D overview and rotatable 3D ribbons show curve response and live position markers. They represent mappings, not electric fields or measured hardware output.

Each channel can select a source axis, inversion, smoothing, background/maximum power and response mode. Global input inversion applies across channels. Channels 2-4 can independently follow Channel 1 pulse repetition or width; linked controls are greyed out.

Power uses `background + (dynamic envelope - background) * curve response`. The background remains when the curve reaches zero; disabled channels, Hard Neutral and unavailable input override it to zero. Several channels can be high together; curves do not normalise to a fixed total.

**Vector volume** is a preset that selects rolling-speed power, a two-second buffer, ratio 20, 40% rest excursion and a 0.5-second return ramp. Position, power and texture share the buffer delay. Per-channel Power envelope selections remain authoritative after applying the preset. Frequency and width damping smooth their response separately. Pulse repetition is 1-255 Hz; equal positive and negative widths are 1-255 us per phase.

Valid edits apply and save automatically. There is no Apply button. See [CONTROL_GUIDE.md](CONTROL_GUIDE.md) for further mapping details.

## Optional Wi-Fi pattern player

Use this when no funscript is available. It runs native ZC95 patterns independently of MFP and Vector curves:

1. Select Wi-Fi and **Output source: Wi-Fi pattern player**.
2. Connect, then click Refresh patterns.
3. Choose a built-in or uploaded pattern and click Play pattern.
4. Adjust its numeric or choice controls while playing. A pattern button appears if supported.

Physical dials control power, with a two-second startup ramp. Stop pattern, Stop hardware, Hard Neutral/Escape, hiding the tab, or connection loss stops playback. Native patterns never automatically restart; press Play again. Vector curve meters remain previews during native playback.

To upload, stop playback, expand Upload a Lua pattern, choose a `.lua` file and click Upload to empty slot. The device validates the script; upload never starts playback or replaces existing scripts. A failed upload can leave the formerly empty slot invalid/occupied. No delete/overwrite control is included. Files must be nonempty and at most 64 KB.

Switching output modes stops the current output and retains Vector settings. Returning to Vector requires reconnecting Wi-Fi and pressing Start output. Numeric/choice controls and the soft button are supported; native audio/display menu widgets are described but not reproduced. The pattern player is a basic companion to the main MFP workflow.

## Validation and limitations

MFP input, Bluetooth output, Wi-Fi dial scaling and basic pattern playback have been tested by the project owner on a ZC95. Automated tests cover curve interpolation, mapping, saved settings, transport filtering, output cancellation, dial following, pattern controls and empty-slot uploads. They do not measure electrical output or certify every firmware/pattern combination. Browser and device responsiveness still matter.

Run automated checks with `python -m unittest discover -s tests` and the Node scripts in `tests/`. `PREVIEW_3D.html` opens a read-only curve visualisation without connecting hardware.

## Project

[Source and releases](https://github.com/Nephet2/Vector-zc95-live) · [ZC95 hardware/firmware](https://github.com/CrashOverride85/zc95)

This is an independent community controller. See [LICENSE](LICENSE) for licensing and attribution.
