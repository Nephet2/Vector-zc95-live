# Vector ZC95 0.6.0 - buffered Vector volume

Close the earlier ZC95 launcher terminal and controller tabs. Run START_VECTOR_ZC95.bat, then open the app in Chrome or Edge. MFP remains ws://127.0.0.1:12355/ws.

Valid adjustments now apply and save automatically. There is no Apply button. Invalid settings stop hardware until corrected and explicitly restarted.

## Buffered Vector volume (0.6.0)

Click Use Vector volume to try the response adapted from your working Vector 1A. It retains power background/maximum ranges and sets channels 1/2 to Vector rolling speed, rest 40%, return ramp 0.5 seconds and volume ratio 20. Channel 3 keeps its chosen response. The preset enables a 2-second output buffer. It applies and saves automatically.

This is a real two-second delay: crossover position, power and texture share the same delayed source timeline. The incoming L0 badge remains live; the graph and output show delayed position. Fill status is displayed. The buffer supplies later received samples for interpolation; it does not predict future data or request future keyframes from MFP.

Vector's five-second rolling mean velocity and thirty-second recent peak are retained for adaptive volume speed. Its ratio formula is ((ratio - 1) + normalized speed) / ratio. Rest reduction and the return ramp act on the excursion above your ZC95 background floor. Power stays between that background and maximum. Short stationary samples do not collapse volume immediately; the rolling-speed response and 0.25-second recency check follow Vector's approach.

The buffer can be disabled for direct timing while retaining rolling volume response, or delay adjusted from zero to five seconds. A changed delay refills at zero output before automatic ramped resumption. Neutral and link-loss stops are immediate rather than delayed. Reconnected sources cannot replay the old source's buffered samples. Stop remains latched as before.

This ports the enabled volume response in your saved working setup. Optional four-phase reversal emphasis, which was disabled in that setup, is not added here. Electrical waveform equivalence is not implied.

## Idle input and recovery (0.5.1)

MFP can send only changed values. A healthy WebSocket/TCP connection now keeps its last position valid while stationary. Motion speed decays to zero, so rest reduction still works. WebSocket ping/pong checks connection liveness; TCP uses connection tracking and OS keepalive. Closing or losing that source pauses its commands at zero. A new connection must provide a new command before the old source can be used again. UDP has no persistent session and retains its expiry policy.

Start output requests ongoing operation. Unexpected input, local API or BLE interruptions pause at zero without cancelling that request. The app retries the already-selected ZC95 without opening a new chooser and ramps back in once the connection and input are healthy. Paused / auto-resume status is shown explicitly. Keep the tab visible; hiding it pauses output and returning can resume it. Closing the page cancels the request.

Stop output, Hard Neutral and manual Disconnect latch off and cancel all retries. Press Start output to run again. Explicit Demo/source actions also cancel the run request. Reloading the page starts disarmed. Bluetooth reconnection after changing a battery or device state depends on the browser retaining its permission and the box being in BLE remote mode.

## Compact layout

Channels 1 and 2 are side by side in a compact two-column dashboard. Channel 3 and crossover sit below; channel 3 starts collapsed with live readouts visible. Expand its controls when needed. At browser widths below 820 pixels the app uses one column. The compact layout is intended for use beside MFP; exact fit depends on display resolution and browser scaling. Stop output remains in the sticky toolbar. MFP connection/help is collapsed.

## Full-range output

The extra software test cap has been removed. Sent commands follow the configured power envelope and crossover, from 0 to 100 percent, with the existing two-second startup ramp. In Scale mode the ZC95 itself applies the physical dial multiplier. The software does not multiply twice.

Review saved background and maximum values, especially high values used for visual testing in previous versions. Start physical dials at zero and raise gradually. Connect in Chrome or Edge, confirm Scale mode, select fresh MFP input or Demo, then press Start output.

The run-duration limit is removed. Output continues until Stop or a stop condition. The command-feed watchdog, stale-input stop, startup ramp and disconnect handling remain active. Existing v2 settings remain compatible; no settings file is included in the ZIP. Copy your settings-zc95-v2.json if desired.

## Stop and scaling

Normal stop disables all four channels and clears all commanded power. Hard Neutral/Escape, stale input, invalid settings, communication failure and hiding the tab stop output. Communication failure triggers disconnect. Unexpected link interruptions pause output at zero and automatically resume with the two-second ramp while Run remains requested. Manual Stop, Hard Neutral, Disconnect and explicit source changes cancel automatic resumption. Channel 4 stays off.

The timer and watchdog run in this browser, not on the device. Keep the tab visible and physical controls accessible: a frozen browser can delay its timer. Actual BLE throughput and device disconnect delay remain to be tested on your PC.

In Scale mode the firmware multiplies the remote command by the physical dial setting. Software does not multiply twice. The BLE interface cannot read this mode; the checkbox records your selected device configuration. Percentages are command levels, not measured watts or perceived intensity.

## Mapping

Running power equals background plus (envelope minus background) times crossover share. Neutral, stale input and disabling a role override background to zero. The startup ramp additionally modifies this command.

AB/CD are channel roles rather than four-phase field steering. Channels 1/2 share L0, blending from 40 to 60 percent by default; channel 3 is independent. Shared smoothing defaults to zero. Frequency and pulse width have independent damping. Vector-like texture selects speed/position blends while retaining ranges. Existing v2 settings remain compatible.

## Checks

Run python -m unittest discover -s tests -v and node tests/test_ble.cjs for engine, transport, API and simulated BLE checks. Actual live device timing still needs verification. If the UI reports a version mismatch, close old launcher terminals and restart this release.

The T-code parser and WebSocket receiver are reused from Vector 1A under the included MIT LICENSE.


## v0.6.1: Follow AB texture
Channels 2 and 3 can independently follow channel 1 pulse repetition frequency and pulse width. Checked controls turn grey; their saved independent settings return when unticked. The follower copies AB’s calculated command, including its damping. Power and source availability remain independent. If AB is inactive, its displayed idle texture values are followed.

Vector volume is a preset, not an extra power multiplier or an override. It selects Vector rolling speed on channels 1/2 and configures delay, ratio, rest and ramp. The Power envelope dropdown always determines the current response. Buffer delay is a separate global setting; rolling-speed response can run with delay disabled.
