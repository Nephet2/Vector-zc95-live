# Control guide

## Power and physical dials

Background minimum is the running floor, including outside the crossover region. Maximum is the top of the configured envelope:

`command = background + (envelope - background) * crossover share`

Rest reduction affects only the excursion above background. Neutral, disabled channels and unavailable input override power to zero. Startup/resume adds a two-second ramp. There is no extra test cap or duration limit.

In device Scale mode the physical dial multiplies the remote command. For example, 50% remote with a 20% dial gives approximately 10% of the firmware commanded scale. This is not measured watts or sensation. The app does not multiply twice. The Scale checkbox confirms your device setting; BLE cannot read that mode.

Green bars show configured ranges. Gold markers/readouts show calculated commands, not measured electrical output or confirmed output-state readback.

## Response modes

| Response | Meaning |
| --- | --- |
| Fixed / maximum | Uses maximum; optional rest reduction still applies |
| Position | Follows script position |
| Speed | Follows motion speed against configured reference |
| Inverse speed | Reverses speed response |
| Position + speed | Mixes position and speed |
| Inverse position + speed | Mixes reversed position and speed |
| Vector rolling speed | Power response using adaptive rolling velocity |

Speed mix controls blend modes. Full-speed reference of 100%/s means one complete script range per second. Rest level reduces modulation when motion stops; return ramp eases it back when movement returns. Response damping slows parameter changes. Texture has independent damping, so it need not compress crossover travel. Shared position smoothing defaults to zero.

## Vector volume versus Vector rolling speed

**Use Vector volume is a preset button, not a separate overriding layer.** It selects Vector rolling speed for channel 1/2 power and sets delay 2 seconds, ratio 20, rest 40%, return ramp 0.5 seconds and power damping zero. Existing background/max values remain. Channel 3 retains its response.

The power dropdown remains authoritative after clicking the preset. Rolling speed can run without look-ahead. The global buffer is separate and delays all source-dependent position, crossover, power and texture together. The incoming badge is live; graph/output follow the delayed timeline. It buffers received samples, not predictions or future funscript keyframes requested from MFP.

Rolling velocity uses a five-second mean and thirty-second recent peak. The normalized response is `(ratio - 1 + normalized_speed) / ratio`. At ratio 20 the moving contribution spans 95-100% before rest/ramp/crossover. Rest reduction creates a larger change. This deliberately differs from directly mapping instantaneous speed across the whole range.

## Follow 1-AB texture

Channels 2 and 3 have separate Follow 1-AB checkboxes for pulse repetition and width. A checked parameter copies AB's calculated value, including damping. Its local controls turn grey, and its saved independent values return when unticked. Power and source availability remain independent. When AB is inactive, followers copy its displayed idle texture values.

Pulse repetition is 1-255 Hz. Pulse width is 1-255 microseconds per phase, with equal positive and negative phase widths. These controls shape firmware-generated pulses; they do not stream arbitrary waveforms.

## Crossover and source

Centre/width set the blend band. Linear and softened curves change its shape. Gap removes modulation above background inside the band. Shared source, inversion, smoothing and speed reference control channels 1/2 while crossover is enabled. Channel 3 has its own source. Demo is synthetic input and explicitly switching it cancels Run.

Healthy WebSocket/TCP input holds the last position if MFP sends only changes. Motion speed still decays. UDP expires after its interval plus two seconds. Source loss pauses immediately rather than draining the delayed buffer. New connections must send new input.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Localhost unavailable | Keep launcher open; read its error; use 127.0.0.1:8766 |
| Bluetooth unavailable | Desktop Chrome/Edge, adapter and OS support |
| Repeated brief connections | Close competing BLE apps/tabs; confirm BLE remote mode |
| Connected but no output | Start output, Scale confirmation, dials, Enabled, input and Neutral state |
| Graph lags MFP | Look-ahead intentionally delays output |
| Texture controls grey | Untick the corresponding Follow 1-AB checkbox |
| Dials work only below a threshold | Select Scale rather than Limit on the device |
| Version mismatch | Close old launcher windows and tabs; launch current release |

Stop hardware, Hard Neutral and manual Disconnect cancel automatic resumption. Unexpected interruptions pause and retry while Run remains requested. Hiding the tab pauses; returning may resume. Stop explicitly when you want it to stay stopped.
