# Usage
- Manage multiple float tracks from the timeline header list.
- Drag points to edit keyframes or use the inspector for numeric edits.
- Toolbar to change interpolation, duration, sample rate, and to add/remove tracks.
- Right-click to move playhead or open track context menus. Export CSV from toolbar for `time_s` + `track_<name>` columns.
- Telemetry panel enables UDP streaming; use the **Telemetry** menu to toggle Debug Log and switch between JSON or binary float payloads before playback.
- Built-in helpers: `tools/udp_recv.py` (JSON), `tools/telemetry_binary_receiver.py` / `tools/telemetry_binary_sender.py` (binary).
