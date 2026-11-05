<div align="center">

# Project Recl/\mr

**Reclaim your data big tech is so hungry for, in a browser tab.**

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)

<img src="docs/screenshots/music-spotify-desktop.jpg" alt="The music player" width="860">

</div>

## Quickstart

```bash
git clone https://github.com/rxjdeep/reclmr.git
cd reclmr && ./install.sh
```

Open **http://localhost:8899** and type the passcode the installer prints. That is the whole setup, about a minute.

You need Linux or macOS and Python 3.10+. The installer asks one thing, where your music is. **Songs in that folder just play**: there is no media server to install.

<details>
<summary>Other ways to run it</summary>

- **By hand, no background service:** `./install.sh --no-service`, then `.venv/bin/python app.py`.
- **From your phone:** put [Tailscale](https://tailscale.com) in front of it, two minutes: [Setup](docs/SETUP.md#remote-access).
- **Without questions** (scripts, CI): `./install.sh --yes`. Windows is experimental and untested.

</details>

## What it is

A self-hosted web app that turns the computer under your desk into a photo library, file manager, music player, audiobook reader and control panel. Open it from your phone or laptop. No accounts, no subscriptions, and your files stay on your machine.

- **Music:** plays straight from a folder of files. Playlists are plain `.m3u8` files, lyrics are synced (`.lrc` files or LRCLIB), and a quality setting saves mobile data. Already run Navidrome? Point reclmr at it instead ([how](docs/SETUP.md#navidrome-optional)).
- **Gallery:** your camera roll and screenshots by day, with a full-screen viewer.
- **Files:** a Finder-style browser with upload, search and a Trash.
- **Audiobooks:** PDF, JSON and TXT books with a voice that reads along.
- **AI:** chat through Ollama, images through ComfyUI, and a voice assistant.
- **Terminal:** a real shell in the browser, locked behind an authenticator-app code.
- **My Lab and Logs:** live stats for your machines, and a record of every sign-in and deletion.

Every part is optional. Anything that needs an outside service tells you what is missing.

## Screenshots

<p align="center">
  <img src="docs/screenshots/music-phone.jpg" alt="Music on a phone" width="860"><br>
  <img src="docs/screenshots/mobile.jpg" alt="Gallery, viewer, Files and Logs on a phone" width="860">
</p>

## More

- [Setup](docs/SETUP.md): reaching it from your phone, the terminal code, every setting, updates.
- [Android apps](docs/ANDROID.md): the app and the phone backup.
- [Security](SECURITY_AUDIT.md): how it is locked down, and what is left.

It listens on localhost only, so you put a tunnel such as Tailscale Funnel in front of it. Sign-in uses a passcode, never kept in the browser. Every file path is checked. There is no telemetry; lyrics are looked up on LRCLIB (the artist and title only).

## Develop

```bash
pip install -r requirements-dev.txt && python -m pytest -q
```

See [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Use it, change it, host it for your family.
