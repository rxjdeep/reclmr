"""Version info route for About panel.

Single source of truth: VERSION below, which must match CHANGELOG[0].
`date` shown in the About panel is the release date of that entry.
"""
import json
from flask import Blueprint, jsonify

bp = Blueprint('version', __name__)

VERSION = "0.8.6"

CHANGELOG = [
    {
        "version": "0.8.6",
        "date": "2026-11-07",
        "changes": [
            "music search: genre results and search history",
            "Searching matches genres: a Genres chip and shelf open that genre",
            "Search keeps your last 12 searches (Enter or opening a result), shown on the Search page, with remove and clear",
        ]
    },
    {
        "version": "0.8.5",
        "date": "2026-11-06",
        "changes": [
            "music home: Recently added shows songs, not albums",
            "The Recently added shelf on the music home screen lists individual songs, newest first",
            "Its Show all link opens the full Recently Added song list",
        ]
    },
    {
        "version": "0.8.4",
        "date": "2026-11-05",
        "changes": [
            "With Navidrome, songs now play straight from the file on disk",
            "Navidrome stays the library backend (tags, playlists, stars, covers)",
            "the audio no longer passes through it",
            "The file is found by the exact size Navidrome reports (its own path is made up on some setups), so no settings are needed",
            "Quality conversions and quick-start copies also come from the local file, reusing copies already made",
            "A song whose file is not on this machine still plays through Navidrome as before",
            "X-Reclmr-Via: file or navidrome on a stream response shows which path a song took",
        ]
    },
    {
        "version": "0.8.3",
        "date": "2026-11-05",
        "changes": [
            "Simple install: one command, no media server, and the installer no longer stops early",
            "README: clone, run ./install.sh, open localhost:8899",
            "The installer asks where your music is",
            "voice models (~230 MB) are now optional",
            "./install.sh --no-service sets up without starting anything",
            "--yes asks nothing",
            "Fixed: without Tailscale the installer exited before printing the passcode and address",
            "Shorter finish: address, passcode and music folder instead of a page of tunnel instructions",
            "Docs: Music section (files by default, Navidrome optional)",
        ]
    },
    {
        "version": "0.8.2",
        "date": "2026-11-05",
        "changes": [
            "First open of a big music folder no longer waits for the scan",
            "The library appears at once (titles from file names) while a background thread reads the tags and fills them in",
            "A small notice shows how many songs are left",
            "The saved copy of the library now also speeds up the next open without Navidrome",
        ]
    },
    {
        "version": "0.8.1",
        "date": "2026-11-05",
        "changes": [
            "Quality setting, quick-start copies, lyrics files and Opus work without Navidrome",
            "Lower-quality MP3 copies are made with ffmpeg straight from the file, kept, and seekable",
            "Slow-to-start m4a/opus files get a quick-starting copy from the file itself",
            "A .lrc file next to a song gives synced lyrics",
            "Opus files are part of the library",
            "Lyrics worked only for songs in the top folder",
            "now every song",
        ]
    },
    {
        "version": "0.8.0",
        "date": "2026-11-05",
        "changes": [
            "Playlists now work without Navidrome",
            "Playlists are plain .m3u8 files in playlists/ (any other player can open them, a file dropped in shows up)",
            "Create, rename, delete, add, remove, reorder and playlist pictures all work from the music folder alone",
            "The 'Showing tags read from the files' notice is gone: reading the files is the normal way now",
        ]
    },
    {
        "version": "0.7.31",
        "date": "2026-11-04",
        "changes": [
            "Playback recovers by itself when a song stalls",
            "A song whose position stops moving for 6 s reloads from where it was",
            "a second failure asks for the converted copy",
            "a third says so",
            "What the player saw (waiting, stalled, error, cut-short ends) is kept for diagnosis: copy(localStorage.mzDiag)",
        ]
    },
    {
        "version": "0.7.30",
        "date": "2026-11-04",
        "changes": [
            "Fewer stalls: stop the endless background polling, time-limit slow requests",
            "Home-screen stat chips only poll while the home screen is showing, one request at a time, 8 s limit",
            "The pairing-request poll pauses in hidden tabs and gives up after 8 s",
            "/api/system answer is reused for 2 s (it ran several programs per call)",
            "Service worker serves a saved copy when the network has not answered in 8 s",
            "Requests slower than 2 s are logged to the journal as [slow] with how many were in flight",
            "Cache-bust counter only moves when a cached file changed",
        ]
    },
    {
        "version": "0.7.29",
        "date": "2026-11-04",
        "changes": [
            "Queue rows now swipe right to remove, like the other swipes",
            "Red Remove label moved to the left edge",
        ]
    },
    {
        "version": "0.7.28",
        "date": "2026-11-04",
        "changes": [
            "Swiping a song out of the queue works on the phone again",
            "A blanket touch-action rule was letting the browser take the sideways drag",
            "the queue rows now keep it",
        ]
    },
    {
        "version": "0.7.27",
        "date": "2026-11-04",
        "changes": [
            "Fix the causes of the music/gallery drop-outs found in review",
            "Full session table drops the least recently used session, not the oldest",
            "The page fetches its CSRF token itself in a fresh tab, so first POSTs are no longer refused (403)",
            "A lost session shows the passcode screen instead of a silent player",
            "Script-load retries are capped across all files, with a Reset link on the recovery screen",
            "Quality badge reads what the server really sent (X-Reclmr-Served)",
            "Queue panel: 60 rows with Show more, follows resizes, and floats over the page on narrow windows",
            "Spotify Modern skin uses colour tokens",
            "App usage log is capped, validated and written atomically",
            "bump_version.py moves the cache-bust numbers",
            "scripts/e2e_smoke.py browser smoke test",
        ]
    },
    {
        "version": "0.7.26",
        "date": "2026-11-03",
        "changes": [
            "Session table no longer evicts real sessions",
            "Raise session cap from 50 to 500 so logins (and test logins) stop kicking you out",
        ]
    },
    {
        "version": "0.7.25",
        "date": "2026-11-02",
        "changes": [
            "Spotify Modern theme for the desktop player",
            "New theme: Spotify Modern (profile menu > Theme), the newer Spotify web look: rounded floating panels, a dark search pill, a floating player card and a white play button",
            "Spotify Classic is still there and unchanged",
            "the choice is remembered",
            "Playlist rows, the queue panel and the quality badge work the same in both",
        ]
    },
    {
        "version": "0.7.24",
        "date": "2026-11-02",
        "changes": [
            "Desktop music: a queue panel you can show and hide, and the quality badge in the player bar",
            "The queue button in the desktop player bar now opens a queue panel beside the page (press Q too) instead of taking you to a separate page",
            "The panel stays open while you browse, follows the song and any change to the queue, and jumps to a song when you click it",
            "The player bar shows what is playing (FLAC Lossless, MP3 kbps, or the converted rate), like the phone player",
            "click it to change streaming quality",
        ]
    },
    {
        "version": "0.7.23",
        "date": "2026-11-02",
        "changes": [
            "Fix the endless reload loop (only the logo showing) when a script fails to load",
            "A script that failed to load made the page reload again and again, because the saved mark was wiped before it could be checked",
            "now it retries once a minute, then shows the recovery screen",
            "The first script now loads from the saved copy like the rest",
        ]
    },
    {
        "version": "0.7.22",
        "date": "2026-10-31",
        "changes": [
            "Files: a proper file manager (new folder, rename, copy/cut/paste, drag to move, details pane)",
            "New folder, rename in place (F2), cut / copy / paste (Ctrl+X/C/V) and drag-and-drop to move or Ctrl-drag to copy",
            "Command bar that follows the selection, a details pane with previews, a storage meter and an editable path bar (Ctrl+L)",
            "Rubber-band selection, resizable columns, type-to-jump, Shift/Ctrl multi-select and full keyboard control",
            "Phone: long-press to pick several files with checkmarks, a Places drawer, and a two-line list that adapts to any width",
            "Colour-coded file types with a two-tone folder icon",
            "Fixed the Up button and Backspace (a variable was shadowing the function) and permanent delete from Trash never reporting success",
        ]
    },
    {
        "version": "0.7.21",
        "date": "2026-10-31",
        "changes": [
            "Spotify playlist links: playlists made by people work",
            "Spotify keeps the pictures of playlists made by people on a second image host, which was refused as unexpected",
            "both hosts are accepted now (for playlist and artist links), any other host still is not",
        ]
    },
    {
        "version": "0.7.20",
        "date": "2026-10-31",
        "changes": [
            "Your own picture for a playlist",
            "Playlist menu (right-click, long-press or the three dots) has Change cover",
            "Upload a photo from your device, or paste a Spotify playlist link to use the picture Spotify shows for it",
            "Remove this cover goes back to the mosaic",
            "The picture is cut to a square from the middle and used everywhere the playlist shows, including the page colour",
            "Deleting a playlist removes its picture",
        ]
    },
    {
        "version": "0.7.19",
        "date": "2026-10-31",
        "changes": [
            "Use the browser's own two-finger back/forward swipe",
            "Removed the home-made swipe handler and its arrow",
            "The page no longer switches off the browser's sideways overscroll, so Chrome and Brave's own two-finger swipe goes back and forward, as on YouTube",
            "Pull-to-refresh and up/down rubber-banding stay off",
        ]
    },
    {
        "version": "0.7.18",
        "date": "2026-10-31",
        "changes": [
            "Touchpad swipe always shows its arrow",
            "A sideways swipe now always shows the arrow, in grey when there is no earlier screen to go back to, so it no longer looks dead at the start of the app",
        ]
    },
    {
        "version": "0.7.17",
        "date": "2026-10-31",
        "changes": [
            "Touchpad swipe now works with a real, slightly wobbly finger",
            "The back/forward swipe adds up the whole movement instead of deciding from the first few events, so a bit of up-and-down drift no longer cancels it",
            "Touchpads that report movement in lines work too",
            "A swipe over something that can still scroll sideways scrolls it",
        ]
    },
    {
        "version": "0.7.16",
        "date": "2026-10-31",
        "changes": [
            "Desktop: right-click menu on playlists, touchpad swipe and scroll",
            "Right-clicking a playlist (in the sidebar, on its page header, or on a card) opens a small menu at the pointer: Play, Shuffle play, Play next, Add to queue, Rename, Delete",
            "Arrow keys and Escape work in that menu",
            "A two-finger swipe sideways on a touchpad goes back or forward in any part of the app, with an arrow that follows the swipe",
            "Scrolling with two fingers over the volume bar changes the volume",
        ]
    },
    {
        "version": "0.7.15",
        "date": "2026-10-31",
        "changes": [
            "Skipping songs: one simpler, safer path",
            "One shared way to make and keep a converted song, instead of two copies of the same code",
            "A long file (an audiobook) is no longer copied before it plays",
            "The look-ahead check reads at most 1 MB even if the server ignores the range",
            "Quick skips get the neighbours of the song they end on, not of every song passed",
            "Covers kept ahead are dropped in order and never leak",
        ]
    },
    {
        "version": "0.7.14",
        "date": "2026-10-30",
        "changes": [
            "A short README",
            "README: 64 lines instead of 233 (what it is, how to run it, what is inside, a few screenshots)",
            "the details moved to docs/SETUP.md and docs/ANDROID.md",
        ]
    },
    {
        "version": "0.7.13",
        "date": "2026-10-30",
        "changes": [
            "Skipping songs is fast",
            "Skipping: the covers and the first stretch of the next songs are fetched ahead, so a skip shows the cover and starts the song at once (about 0.6 s instead of 5 s on a slow connection)",
            "Songs whose file made the browser wait (an index at the end, or a cover picture inside, common in m4a and opus files) get an audio-only copy made once and kept, made ahead for the next songs",
            "The next two songs are converted ahead, in every quality",
        ]
    },
    {
        "version": "0.7.12",
        "date": "2026-10-28",
        "changes": [
            "Lyrics: tell versions of a song apart by listening",
            "Lyrics: when the lyrics site has several different versions of a song with the same length (an alternate take, a mislabelled upload), the first seconds of the song are listened to with the server's speech model and the set of lyrics that fits is used, once per song",
            "Saved lyrics are looked up again",
        ]
    },
    {
        "version": "0.7.11",
        "date": "2026-10-28",
        "changes": [
            "Lyrics must match the song",
            "Lyrics: a search hit from LRCLIB is used only if its title and artist match the song playing (it used to take the closest length, so a different song of about the same length could win)",
            "saved lyrics are looked up again",
            "Fixed a Python warning from an old changelog line",
        ]
    },
    {
        "version": "0.7.10",
        "date": "2026-10-28",
        "changes": [
            "No stop in the middle of the swipe down",
            "Now Playing: swiping it away no longer restarts the slide a moment after you let go (the history step did), which was the stop in the middle of the animation",
            "Android app: vibrations no longer make the page wait for the system, which stalled the swipe at the buzz",
        ]
    },
    {
        "version": "0.7.9",
        "date": "2026-10-28",
        "changes": [
            "Smoother Now Playing swipe",
            "Now Playing: the sheet is positioned once per frame, no longer rebuilds its content or the page behind it when it opens or closes, and no longer blocks the browser while you drag it",
            "You can grab it while it is still sliding: it stops under your finger and the direction you were going decides where it settles",
        ]
    },
    {
        "version": "0.7.8",
        "date": "2026-10-28",
        "changes": [
            "Songs change with the screen off",
            "Android app: the CPU and Wi-Fi locks are kept through the gap between songs (they were released the moment a song ended, so a sleeping phone only started the next song when you woke it)",
            "The app is exempted from Doze when installed",
        ]
    },
    {
        "version": "0.7.7",
        "date": "2026-10-27",
        "changes": [
            "Sign-in comes before the walkthrough; clearer passcode wording",
            "Sign-in: the first-run walkthrough now waits until you are signed in, so the name you enter is saved",
            "Login: it says passcode (not password) and tells you where to find it",
        ]
    },
    {
        "version": "0.7.6",
        "date": "2026-10-27",
        "changes": [
            "Your name in the home prompt; tests no longer touch settings.json",
            "Setup asks what to call you, and the home prompt reads yourname@reclmr:~$ (change it in Settings, You)",
            "Tests: the suite now uses its own settings file instead of the real settings.json",
        ]
    },
    {
        "version": "0.7.5",
        "date": "2026-10-27",
        "changes": [
            "Terminal-style home title",
            "Home: the title is a minimal terminal prompt (reclmr@<this machine>:~$ with a blinking cursor), centred at the top",
        ]
    },
    {
        "version": "0.7.4",
        "date": "2026-10-27",
        "changes": [
            "Heavier Halo-style home title",
            "Home: the title is drawn as heavy, wide, cut-corner letters with an orange glowing A under the ring arc (drawn for the app",
            "no font file needed)",
        ]
    },
    {
        "version": "0.7.3",
        "date": "2026-10-27",
        "changes": [
            "Home title in Michroma",
            "Home: the title is set in Michroma, a wide squared face close to the Halo lettering (SIL Open Font License, listed in THIRD_PARTY_NOTICES)",
        ]
    },
    {
        "version": "0.7.2",
        "date": "2026-10-27",
        "changes": [
            "Halo-style home title, centred, no tagline",
            "Home: the title is now a centred Halo-style mark (a ring arc with ticks, angular letters, an orange Forerunner glyph for the A)",
            "the tagline is gone",
        ]
    },
    {
        "version": "0.7.1",
        "date": "2026-10-27",
        "changes": [
            "Home screen wordmark",
            "Home: a wordmark title (recl/\\mr with the slash pair drawn as an accent-gradient A) and a small tagline above the clock",
        ]
    },
    {
        "version": "0.7.0",
        "date": "2026-10-27",
        "changes": [
            "Renamed everywhere to reclmr: files, settings, apps",
            "Name: every file, folder, setting, cookie, storage key and Android package now says reclmr (nothing says the old name except the LICENSE copyright line the MIT licence requires)",
            "Settings: RECLMR_* only, so rename the old-prefix keys in your .env",
            "Command and service: ./reclmr and the reclmr service",
            "Android: new package IDs io.reclmr.app and io.reclmr.pusher (uninstall the old apps",
            "sign in again)",
            "Sign in again once: the session cookie has a new name",
        ]
    },
    {
        "version": "0.6.8",
        "date": "2026-10-27",
        "changes": [
            "README: shorter, current features only, Windows marked experimental",
            "README rewritten: one features list, current music, Files and Android behaviour, Windows marked experimental with a note to set a passcode, no stale test counts",
        ]
    },
    {
        "version": "0.6.7",
        "date": "2026-10-27",
        "changes": [
            "reclmr: README and commands renamed",
            "README: every mention is now reclmr",
            "settings use the RECLMR_ prefix",
            "Command: ./reclmr",
            "Installer: installs create the reclmr service",
            "Android apps are labelled reclmr and reclmr Backup",
        ]
    },
    {
        "version": "0.6.6",
        "date": "2026-10-26",
        "changes": [
            "Onboarding QR asks for the tunnel address when opened on localhost",
            "Onboarding: opened on localhost or a home-network address, the phone QR step now explains a tunnel is needed and makes the QR from the tunnel address you paste, instead of a QR for an address a phone cannot reach",
        ]
    },
    {
        "version": "0.6.5",
        "date": "2026-10-26",
        "changes": [
            "README screenshots without the old name",
            "README: the Logs screenshot is the real Logs page again and the phone strip shows it too",
            "no image shows the old name",
        ]
    },
    {
        "version": "0.6.4",
        "date": "2026-10-26",
        "changes": [
            "Music screenshots in the README",
            "README: Music section with the Spotify theme, the Glossy Black theme and the phone player",
        ]
    },
    {
        "version": "0.6.3",
        "date": "2026-10-26",
        "changes": [
            "Install scripts read the phone address from .env",
            "Install scripts take the phone address from RECLMR_PHONE in .env instead of a built-in default",
            ".env.example documents RECLMR_PHONE",
        ]
    },
    {
        "version": "0.6.2",
        "date": "2026-10-26",
        "changes": [
            "Renamed to Project Reclmr, smoother scrolling, covers load ahead",
            "Name: Project Recl/\\mr (reclmr in files and commands) in the page, install name and README, reclmr on the Android launchers, fork credit to reclmr",
            "Scrolling: covers load two screens ahead, the page layer is released after each slide, correct row height estimate",
            "Android: left-edge back setting is restored reliably, permission re-granted on every install",
        ]
    },
    {
        "version": "0.6.1",
        "date": "2026-10-26",
        "changes": [
            "Uploads, trash and places in Files, streaming quality, lyrics, multi-select playlists, native-feel touches, new backup app",
            "Files: upload from the device, Trash with permanent delete, editable Places, folders can be trashed",
            "Music: streaming quality (transcode cache, slider for Wi-Fi and mobile data), live lyrics line, playing indicator and Playing from playlist, playlist rename and delete with undo",
            "Playlists: select several songs to move or remove, swipe the mini player for next and previous, green tick for songs already in a playlist",
            "Feel: pull to refresh, touch-down feedback, edge swipe back, instant startup from the saved page, artist names in song rows are plain text",
            "Backup app: Holo look, resumable uploads, Wi-Fi only, stop button",
            "Android app: keep the screen on in Now Playing, left back swipe off while open, Liked Songs and Search shortcuts, share text into Search",
        ]
    },
    {
        "version": "0.6.0",
        "date": "2026-10-25",
        "changes": [
            "Music: lyrics, artist photos and banners, Spotify-style player and search; phone backup app",
            "Lyrics under the cover (synced line, romaji for Japanese, LRCLIB fallback) and a desktop lyrics page",
            "Artist photos and banners from Spotify, SoundCloud and Deezer with a picker in the artist menu",
            "Now Playing laid out like Spotify, file format line and details sheet, player is no longer a history step",
            "Playlist delete with Undo, long-press menus on albums/artists/playlists, drag to reorder on desktop, swipe a row to queue",
            "Desktop add-to-playlist card, home screen Now Playing card, SSD usage chip, page-image mode for illustrated PDFs",
            "Phone backup intake (routes/backup.py) and the Reclmr Backup app with a Holo look",
            "Library cached on the phone for an instant music screen, Music reopens where you left it",
        ]
    },
    {
        "version": "0.5.0",
        "date": "2026-10-23",
        "changes": [
            "Gallery, Files browser, Logs, two-step Terminal, XSS hardening",
            "Gallery: iOS/Google-Photos style library with viewer",
            "Files: Finder/Nautilus style browser over the whole machine (opt-in via RECLMR_BROWSE_ROOT)",
            "Terminal needs a TOTP code (scripts/totp_setup.py)",
            "Logs screen with audit trail",
            "CSP: no CDN, no inline scripts, many XSS sinks escaped",
            "Music: glossy and Spotify themes, Connect, visualizer",
            "Router: back/forward navigation",
        ]
    },
    {
        "version": "0.4.1",
        "date": "2026-10-11",
        "changes": [
            "Fix Windows CI (musicgen test file handle)",
            "Tests: close streamed audio before deleting, so the suite passes on Windows",
        ]
    },
    {
        "version": "0.4.0",
        "date": "2026-10-11",
        "changes": [
            "My Lab: whole-homelab overview card in three styles",
            "System screen is now My Lab: one iPhone-sized card for this machine plus paired devices, with Neofetch, Rack and Constellation styles and a screenshot mode",
            "Add devices Bluetooth-style: Find devices on my Wi-Fi, tap Add, check both screens show the same 6-digit number, tap Allow",
            "Device stats travel over HTTPS pinned to each device's own certificate; keys only unlock stats and can be reset anytime",
            "Reclmr stays localhost-only unless you turn on Let other devices add this computer",
            "Headless boxes (Pi, NAS, Proxmox) run a tiny stats-only agent: one command, approves in the terminal, starts on boot",
            "Shows Docker/Podman containers, loaded Ollama models, chosen systemd services and top processes",
            "Fix: opening a #screen link no longer crashes before telemetry loads",
        ]
    },
    {
        "version": "0.3.0",
        "date": "2026-10-11",
        "changes": [
            "Polish + fixes; Liquid UI, Music Generator, Model Advisor, ComfyUI lifecycle",
            "Liquid UI: press-squash, ripples and stretchy AI spread (experimental apps stay hidden, disabled buttons dim again)",
            "Music Generator, AI Model Advisor with one-tap downloads, ComfyUI start/stop/log from the UI, neofetch-style System panel",
            "Fix split GGUF downloads deleting themselves when merged",
            "Fix blank Legos (three.js now from jsdelivr, allowed by CSP)",
            "QR codes generated in the browser (no third-party QR service, tunnel URL stays private)",
            "Fix unstyled onboarding button and broken journal mic icon",
            "Agents Recent Activity shows 'No activity yet.' instead of loading forever",
            "Music/ComfyUI generation polls stop on errors and re-enable the button",
            "XSS hardening: data-* attributes instead of inline onclick values, escaped system/ComfyUI fields, removed duplicate escapeHtml",
            "Service worker no longer caches /api/ responses",
        ]
    },
    {
        "version": "0.2.1",
        "date": "2026-09-07",
        "changes": [
            "Polish pass: TUI non-blocking polls, session caching, agent workflow docs",
            "TUI fetches run in worker threads so a slow/offline app never blocks the UI",
            "TUI session token is cached in memory and invalidated on 401",
            "Fixed session-cache bug that skipped loading the saved session",
            "Added comprehensive AGENTS.md + CLAUDE.md workflow (test/bug/dependency/release protocols) for all agents",
        ]
    },
    {
        "version": "0.2.0",
        "date": "2026-09-06",
        "changes": [
            "TUI dashboard: 'reclmr tui'",
            "'reclmr tui' opens a brutalist terminal dashboard (system, voice, music, devices, logs)",
            "Update panel + 'U' action reuse the verified updater",
            "works even when the app is offline",
            "Optional 'textual' dependency via requirements-tui.txt (friendly one-line hint if missing)",
            "Passcode login handled in-TUI and the session is stored in ~/.config/reclmr",
        ]
    },
    {
        "version": "0.1.0",
        "date": "2026-09-06",
        "changes": [
            "Terminal updates: 'reclmr update' CLI",
            "'reclmr update' command (check / update / rollback) shares the in-app updater's verified logic",
            "install.sh symlinks reclmr into ~/.local/bin so it's on PATH",
        ]
    },
    {
        "version": "0.0.6",
        "date": "2026-09-06",
        "changes": [
            "One-click updates: auto-release pipeline, semver compare, supervised restarts",
            "Updater only offers genuine upgrades (semver compare. No more downgrade offers)",
            "GitHub Action auto-creates a git tag + release for each version bump (no manual tagging)",
            "Manual ./reclmr starts now supervise the app so self-update restarts work without systemd",
            "install.sh warns when the install is not a git checkout (updates need git)",
        ]
    },
    {
        "version": "0.0.5",
        "date": "2026-09-06",
        "changes": [
            "Persistent sessions + XSS hardening via event delegation",
            "Sessions now persist across app restarts (sessions.json, chmod 600)",
            "Refactor inline onclick handlers to data-* attributes in file browser, books, and agents (closes quote-breakout XSS)",
            "ProxyFix trusts the tunnel hop so rate limits/backoff are per-client",
        ]
    },
    {
        "version": "0.0.4",
        "date": "2026-09-06",
        "changes": [
            "Security hardening + polish: fix path traversal in books, XSS sinks, and deploy/config issues",
            "Fix arbitrary file read via books routes (book_id/file traversal)",
            "Fix XSS across terminal, agent logs, file browser, reader, and chat (escaped output + single-quote)",
            "Docker: require passcode + secret, localhost-only port, fix .dockerignore secret leak",
            "Remove localhost.run relay from installer (Tailscale/cloudflared only)",
            "Bump cryptography to 50.0.0 to close 11 known CVEs",
            "Sanitize universe names, reject change_pin in open mode, ProxyFix for per-client limits",
            "Add upload size cap and input validation",
        ]
    },
    {
        "version": "0.0.3",
        "date": "2026-09-06",
        "changes": [
            "Voice agent: drives Hermes natively with a persistent session (falls back to local Ollama/cloud when Hermes isn't installed)",
            "Voice agent: modular STT/LLM/TTS engines configurable from Settings → Voice. No terminal needed",
            "Voice agent: command access tiers (Talk / Basic / Full) with a confirmation for unrestricted access",
            "Voice agent: remembers your conversation, can be named, and shows clear errors instead of failing silently",
            "Voice agent: browser or Whisper speech recognition, Piper or browser speech",
            "Security: fixed open-mode auth bypass on fresh installs (duplicate passcode in .env)",
            "Security: fixed path traversal in the music and file-browser routes",
            "UI: voice overlay now matches the black/white minimalism theme",
            "Settings: change your passcode in-app; library paths apply instantly without restart",
            "Devices: real Tailscale device list with names, OS, and online status",
            "Fixes: TTS autoplay on phones, stuck 'speaking' state, book-reader crash, duplicate HTML cleanup",
        ]
    },
    {
        "version": "0.0.2",
        "date": "2026-08-19",
        "changes": [
            "Security: opaque session tokens replace the PIN cookie. The passcode is never stored in the browser",
            "Security: CSRF protection on all state-changing requests",
            "Security: WebSocket terminal/voice sockets require the session token (works over tunnels now)",
            "Security: quick commands run shell-free (allowlisted argv table, no shell=True)",
            "Security: brute-force backoff + rate limits on login; 8-digit passcode default",
            "Security: removed third-party localhost.run relay, Tailscale Funnel only",
            "Security: binds 127.0.0.1 by default; loud warning otherwise",
            "Security: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy headers",
            "Books: correct chapter counts per book (no more 30-chapter cap)",
            "Books: reading position syncs across devices (phone and laptop resume the same spot)",
            "Books: cover generator uses cross-platform fonts",
            "AI chat: consistent default model, input caps, real error messages from summarize/Q&A",
            "Cross-platform: real OS detection (Debian/Fedora/macOS/Windows)",
            "Windows: setup.ps1 installer + reclmr.ps1 lifecycle wrapper; terminal degrades gracefully",
            "Tests: 74 security tests (auth, CSRF, WebSocket, allowlist, traversal, symlinks) + CI on Ubuntu/macOS/Windows",
        ]
    },
    {
        "version": "0.0.1",
        "date": "2026-08-14",
        "changes": [
            "First public release. Experimental alpha",
            "Report issues on GitHub",
            ".env now loaded on manual start (not just systemd)",
            "Settings: library paths save to .env for real",
            "AI chat surfaces model errors instead of hanging",
            "Universe: fixed duplicated empty-state message",
            "Projects: onboarding empty state",
            "ComfyUI: offline install guidance",
            "Notifications built from real system stats",
            "App writes request logs (Logs screen works)",
            "Safari share sheet crash fixed",
            "First-run onboarding walkthrough added",
        ]
    },
]


def _current_entry():
    """Changelog entry matching VERSION; falls back to the newest entry."""
    for entry in CHANGELOG:
        if entry.get('version') == VERSION:
            return entry
    return CHANGELOG[0] if CHANGELOG else {"version": VERSION, "date": "", "changes": []}


@bp.route('/api/version')
def get_version():
    """Return current version and changelog."""
    current = _current_entry()
    return jsonify({
        "version": current["version"],
        "date": current["date"],
        "changelog": CHANGELOG,
    })
