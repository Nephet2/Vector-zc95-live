# Control guide - 0.9.1

See README.md for complete setup, mapping and operating notes.

- Expand a channel to edit its position curve. Drag points, double-click the plot to add, or use the point selector and coordinate fields. Endpoints cannot be removed or moved horizontally.
- Smooth passes through points without overshoot. Linear joins them directly. Presets replace points; smoothing/linear selection is retained.
- Use Fixed/maximum power response for a direct curve-to-power mapping. Other power responses modulate the available envelope first.
- Example: background 2%, dynamic envelope 10%, curve response 25% gives 4% commanded power. With Bluetooth Scale or Wi-Fi dial-follow, a 50% physical dial then gives about 2% of the firmware command scale. These are not measured watts or sensation.
- A zero-height curve means background, not OFF. Disable the channel to command zero.
- Curves do not share a fixed power budget; overlap can raise several channels together.
- Vector volume is a preset for all four power responses and global look-ahead settings, not an additional multiplier or permanent override. Channel dropdowns remain authoritative.
- Follow Channel 1 links frequency and width independently on channels 2-4; grey local settings return when unticked.
- Live markers reflect the applied backend state. Draft curves apply and save automatically. Numeric power feedback is calculated, not output readback.
- Stop hardware cancels automatic resumption. Unexpected connection interruptions pause and can resume with a startup ramp while Run remains requested.

Keep the earlier release in a separate folder. Settings v3 migration details and limitations are in README.md. Do not run both ZC95 launchers on the same ports.

Fresh installs use starter-settings.json, copied from Steve's tested settings. Existing settings-zc95-v3.json wins. Reset defaults returns to the original basic curve configuration, rather than reloading the starter preset.
