# Laptop volume from your phone

A browser can't change a computer's system volume, so a small agent runs on the laptop and takes the phone's − / + presses from the server.

1. Copy `scripts/volume_agent.py` to the laptop (it needs only Python 3; nothing to install).
2. Run it: `RECLMR_URL=https://your-reclmr-address python3 volume_agent.py`. The first run asks for your passcode once and remembers a session.
3. On the phone: music player → the **Connect to a device** button. A **<laptop> volume** row with − and + appears while the agent is running. Each press moves the volume 5 %.

Works with: macOS (`osascript`), Linux with PipeWire (`wpctl`), PulseAudio (`pactl`) or ALSA (`amixer`). It only sets the output volume (0–100 %, never above 100).

To start it at login: macOS, a Login Item or a launchd agent; Linux, a systemd user service or your desktop's autostart. For unattended starts use `--pin-env` and set `RECLMR_PIN`.
