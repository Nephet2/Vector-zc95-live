# Vector-zc95-live

Local MultiFunPlayer (MFP) T-code to ZC95 Bluetooth controller with crossover, background power, dynamic texture and buffered Vector-style volume.

**v0.6.1 | Experimental community software | Windows-first**

Runs locally with Python and Chrome or Edge. No Xeneno account required. Separate from Vector for ReStim/FOCstim, with independent ports and settings.

## Quick start

1. Install Python 3.10+ with Python available on PATH. No pip packages needed.
2. Download Code > Download ZIP and extract it.
3. Run START_VECTOR_ZC95.bat. Keep its terminal open. Open http://127.0.0.1:8766 in desktop Chrome or Edge.
4. Set MFP WebSocket output to **ws://127.0.0.1:12355/ws**, sending L0. TCP/UDP also use port 12355.
5. Put ZC95 in BLE remote mode. Select **Scale** for physical dials. Close competing Bluetooth apps/tabs.
6. Click Connect ZC95, select the device and confirm Scale. Connecting does not start output.
7. Review ranges, start physical dials at zero, provide MFP input, then click Start output.

Author testing used firmware v2.0-rc2. Other firmware/platform combinations need verification.

See [CONTROL_GUIDE.md](CONTROL_GUIDE.md) for controls and troubleshooting; [DEVELOPMENT_NOTES.md](DEVELOPMENT_NOTES.md) for implementation history.

## Channels

| Channel | Role | Default |
| --- | --- | --- |
| 1 | AB | Full share below L0 40% |
| 2 | CD | Full share above L0 60% |
| 3 | Prostate | Independent mapping |
| 4 | Reserved | Off |

Channels 1/2 blend between 40% and 60%. These are software roles, not ReStim/FOCstim phase steering or electrode wiring instructions.

## Settings, operation and updates

Valid edits apply and save automatically in settings-zc95-v2.json beside the launcher. Close the old launcher before updating; copy that file into the new folder to retain your configuration. Downloads exclude personal settings.

Stop hardware cancels Run. Hard Neutral/Escape commands zero and cancels automatic resumption. Unexpected connection loss pauses and retries while Run remains requested. Returning from a hidden tab can also resume. Closing/reloading starts disarmed.

The watchdog depends on browser responsiveness; a frozen browser can delay commands. Physical output is not measured or verified. Keep device controls accessible and follow ZC95 operating instructions. Experimental software, not a medical device.

## Development and issues

Run `python -m unittest discover -s tests -v` and `node tests/test_ble.cjs`. Node is only needed for development. Tests simulate BLE; they do not verify physical waveforms. A real-network test may skip where local sockets are restricted.

Alternate ports: `python server.py --web-port 8767 --mfp-port 12356`. Add `--no-browser` to launch manually.

Report app, firmware, browser and OS versions, input transport and reproduction steps. Review logs for personal information before posting.

## Credits and licence

MIT: see [LICENSE](LICENSE). T-code parsing and WebSocket receiver originate in Vector 1A, with its licence retained. Hardware/firmware: [CrashOverride85/zc95](https://github.com/CrashOverride85/zc95); [BLE protocol](https://github.com/CrashOverride85/zc95/blob/main/docs/BleStreaming.md). Independent community project; no endorsement implied.
