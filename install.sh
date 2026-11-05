#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# reclmr — Installer
# Works on: Linux (systemd), macOS (launchd), WSL
#   ./install.sh                 set up and start it as a background service
#   ./install.sh --no-service    set up only; run it yourself:  .venv/bin/python app.py
#   ./install.sh --yes           never ask a question (take the defaults)
# ═══════════════════════════════════════════════════════════════
set -e

NO_SERVICE=0
ASK=1
for arg in "$@"; do
    case "$arg" in
        --no-service) NO_SERVICE=1 ;;
        --yes|-y) ASK=0 ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    esac
done
[ -t 0 ] || ASK=0      # piped or in CI: no questions

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="reclmr"

# ─── Detect OS ──────────────────────────────────────────────────
OS_TYPE="linux"
if [[ "$(uname)" == "Darwin" ]]; then
    OS_TYPE="macos"
elif [[ "$(uname -r)" == *microsoft* ]] || [[ "$(uname -r)" == *Microsoft* ]]; then
    OS_TYPE="wsl"
fi

echo "╔══════════════════════════════════════════════╗"
echo "║   reclmr — Installer                        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Detected: $OS_TYPE ($(uname -s) $(uname -r))"
echo ""

# ─── One-click updates require a git clone ───────────────────────
# The in-app updater (Settings → About → Check for updates) checks out new
# versions via git. A ZIP/tarball install works fine but can't self-update.
if ! git -C "$APP_DIR" rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    echo "⚠ This is NOT a git checkout — the in-app updater will be unavailable."
    echo "  The app installs and runs fine, but for one-click updates reinstall with:"
    echo ""
    echo "    git clone https://github.com/rxjdeep/reclmr ~/reclmr"
    echo "    cd ~/reclmr && ./install.sh"
    echo ""
fi

# ─── Check Python ───────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYBIN=python3
elif command -v python &>/dev/null; then
    PYBIN=python
else
    echo "✗ Python 3 is required."
    if [ "$OS_TYPE" = "macos" ]; then
        echo "  Install it: brew install python3"
    else
        echo "  Install it: sudo apt install python3 python3-venv"
        echo "  Or:         sudo dnf install python3 python3-devel"
    fi
    exit 1
fi
PYVER=$($PYBIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYVER found"

if [[ "$PYVER" < "3.10" ]]; then
    echo "✗ Python 3.10+ required. You have $PYVER"
    exit 1
fi

# ─── Install uv (fast Python package manager) ───────────────────
if ! command -v uv &>/dev/null; then
    echo "→ Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "✓ uv ready"

# ─── Install qrencode (for QR code) ─────────────────────────────
if ! command -v qrencode &>/dev/null; then
    echo "→ Installing qrencode (for phone QR code)..."
    if [ "$OS_TYPE" = "macos" ]; then
        if command -v brew &>/dev/null; then
            brew install qrencode 2>/dev/null || echo "  (optional — skipped)"
        fi
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y qrencode 2>/dev/null || echo "  (optional — skipped)"
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y qrencode 2>/dev/null || echo "  (optional — skipped)"
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm qrencode 2>/dev/null || echo "  (optional — skipped)"
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y qrencode 2>/dev/null || echo "  (optional — skipped)"
    else
        echo "  (qrencode not found — QR code will be skipped)"
    fi
fi

# ─── Install ffmpeg (music conversion, album art, Whisper STT + Piper TTS) ─
if ! command -v ffmpeg &>/dev/null; then
    echo "→ Installing ffmpeg (music quality setting, voice)..."
    if [ "$OS_TYPE" = "macos" ]; then
        command -v brew &>/dev/null && brew install ffmpeg 2>/dev/null || echo "  (optional — skipped)"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y ffmpeg 2>/dev/null || echo "  (optional — skipped)"
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y ffmpeg 2>/dev/null || echo "  (optional — skipped)"
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm ffmpeg 2>/dev/null || echo "  (optional — skipped)"
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y ffmpeg 2>/dev/null || echo "  (optional — skipped)"
    else
        echo "  (ffmpeg not found — install it manually for voice)"
    fi
else
    echo "✓ ffmpeg ready"
fi

# ─── Tunnel client (for secure HTTPS access from phone) ──────────
# Tailscale Funnel is the only supported tunnel: it terminates TLS on your
# own machine and requires your own tailnet. We deliberately do NOT use
# third-party relays (localhost.run, localhost tunnel via SSH) — those
# forward plaintext HTTP through someone else's box, which contradicts
# reclmr's privacy story. cloudflared (your own Cloudflare account) is the
# fallback.
TUNNEL_TOOL=""

if command -v tailscale &>/dev/null; then
    TUNNEL_TOOL="tailscale"
    echo "✓ Tunnel client ready (Tailscale Funnel)"
elif command -v cloudflared &>/dev/null; then
    TUNNEL_TOOL="cloudflared"
    echo "✓ Tunnel client ready (cloudflared — your own Cloudflare account)"
else
    echo "⚠ No tunnel client available."
    echo "  Install Tailscale: curl -fsSL https://tailscale.com/install.sh | sh"
    echo "  Then: sudo tailscale up  (login to your account)"
    echo "  (Alternative: install cloudflared from developers.cloudflare.com)"
fi

# ─── Create venv + install deps ─────────────────────────────────
echo "→ Creating virtual environment..."
cd "$APP_DIR"
uv venv .venv --python "$PYBIN"
echo "→ Installing dependencies (this takes a minute)..."
uv pip install -r requirements.txt
echo "✓ Dependencies installed"

# ─── Create .env from example if none exists ────────────────────
if [ ! -f .env ]; then
    echo "→ Creating .env from template..."
    cp .env.example .env

    # Generate a random secret key
    SECRET=$($PYBIN -c "import secrets; print(secrets.token_hex(32))")
    if [ "$OS_TYPE" = "macos" ]; then
        sed -i '' "s/change-me-to-a-random-string/$SECRET/" .env
    else
        sed -i "s/change-me-to-a-random-string/$SECRET/" .env
    fi

    # Generate a random 8-digit passcode for app access (longer = harder
    # to brute-force; the app warns if you shorten it below 8 characters)
    PIN=$($PYBIN -c "import secrets; print(''.join(str(secrets.randbelow(10)) for _ in range(8)))")
    # Idempotent: replace any existing PIN line (either name), else append.
    if grep -q '^RECLMR_PIN=' .env 2>/dev/null; then
        if [ "$OS_TYPE" = "macos" ]; then
            sed -i '' "s/^RECLMR_PIN=.*/RECLMR_PIN=$PIN/" .env
        else
            sed -i "s/^RECLMR_PIN=.*/RECLMR_PIN=$PIN/" .env
        fi
    else
        echo "RECLMR_PIN=$PIN" >> .env
    fi
    echo "✓ .env created (edit it to customize paths)"

    # Where the music is. Nothing else is needed to play it: no media server.
    MUSIC_ANS="$HOME/Music"
    if [ "$ASK" = 1 ]; then
        read -r -p "Where is your music? [$MUSIC_ANS] " ANS || true
        [ -n "$ANS" ] && MUSIC_ANS="${ANS/#\~/$HOME}"
    fi
    if grep -q '^RECLMR_MUSIC_DIR=' .env; then
        if [ "$OS_TYPE" = "macos" ]; then
            sed -i '' "s|^RECLMR_MUSIC_DIR=.*|RECLMR_MUSIC_DIR=$MUSIC_ANS|" .env
        else
            sed -i "s|^RECLMR_MUSIC_DIR=.*|RECLMR_MUSIC_DIR=$MUSIC_ANS|" .env
        fi
    else
        echo "RECLMR_MUSIC_DIR=$MUSIC_ANS" >> .env
    fi
fi

# Lock down .env — contains PIN, SECRET_KEY, and any user-supplied tokens.
chmod 600 .env 2>/dev/null || true

# ─── Piper TTS voices (optional, ~230 MB: only the voice assistant and read-aloud use them) ──
WANT_VOICES=0
[ "${RECLMR_VOICES:-}" = "1" ] && WANT_VOICES=1
if [ "$WANT_VOICES" = 0 ] && [ "$ASK" = 1 ]; then
    read -r -p "Download offline voice models for speech (~230 MB)? [y/N] " VANS || true
    case "$VANS" in [yY]*) WANT_VOICES=1 ;; esac
fi
if [ "$WANT_VOICES" = 1 ]; then
PIPER_DIR=$(grep '^RECLMR_PIPER_DIR=' .env 2>/dev/null | cut -d= -f2- | sed 's/^"//;s/"$//')
if [ -z "$PIPER_DIR" ]; then
    PIPER_DIR="$HOME/.local/share/piper"
fi
PIPER_DIR=$(eval echo "$PIPER_DIR")  # expand ~
mkdir -p "$PIPER_DIR"
_fetch_voice() {
    local name="$1" quality="$2"
    local base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/${name}/${quality}/en_US-${name}-${quality}"
    if [ ! -f "$PIPER_DIR/en_US-${name}-${quality}.onnx" ]; then
        echo "→ Downloading Piper voice ${name} (${quality})…"
        curl -sSL "${base}.onnx" -o "$PIPER_DIR/en_US-${name}-${quality}.onnx" \
            || echo "  (voice ${name} download failed — speech will use browser TTS)"
    fi
    if [ ! -f "$PIPER_DIR/en_US-${name}-${quality}.onnx.json" ]; then
        curl -sSL "${base}.onnx.json" -o "$PIPER_DIR/en_US-${name}-${quality}.onnx.json" 2>/dev/null || true
    fi
}
_fetch_voice "lessac" "high"
_fetch_voice "lessac" "medium"
_fetch_voice "kathleen" "low"
else
    echo "  (skipping voice models: speech uses your browser's voice. Add them later: RECLMR_VOICES=1 ./install.sh)"
fi

# ─── SSL certs not needed — tunnel handles HTTPS ────────────────
# The app runs HTTP on localhost only (not exposed). The cloudflared
# tunnel provides trusted HTTPS externally. No local certs needed.

PORT=$(grep "^RECLMR_PORT=" .env 2>/dev/null | tail -n1 | cut -d= -f2 || echo "8899")
PORT=${PORT:-8899}
if [ "$NO_SERVICE" = 1 ]; then
    PIN=$(grep "^RECLMR_PIN=" .env 2>/dev/null | tail -n1 | cut -d= -f2)
    MUSIC=$(grep "^RECLMR_MUSIC_DIR=" .env 2>/dev/null | tail -n1 | cut -d= -f2)
    echo ""
    echo "✓ reclmr is set up (nothing was started)."
    echo ""
    echo "  Run it:     cd $APP_DIR && .venv/bin/python app.py"
    echo "  Open:       http://localhost:${PORT}"
    echo "  Passcode:   ${PIN}   (kept in .env)"
    echo "  Music:      ${MUSIC:-~/Music}   (just put songs there)"
    exit 0
fi

# ─── Service setup (platform-specific) ──────────────────────────
echo ""
PORT=$(grep "^RECLMR_PORT=" .env 2>/dev/null | tail -n1 | cut -d= -f2 || echo "8899")

if [ "$OS_TYPE" = "macos" ]; then
    echo "→ Setting up macOS LaunchAgent..."
    LAUNCH_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$LAUNCH_DIR"
    PLIST_FILE="$LAUNCH_DIR/com.reclmr.app.plist"

    cat > "$PLIST_FILE" << 'PLISTEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.reclmr.app</string>
    <key>WorkingDirectory</key>
    <string>__APP_DIR__</string>
    <key>ProgramArguments</key>
    <array>
        <string>__APP_DIR__/.venv/bin/python</string>
        <string>__APP_DIR__/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__APP_DIR__/reclmr.log</string>
    <key>StandardErrorPath</key>
    <string>__APP_DIR__/reclmr.log</string>
</dict>
</plist>
PLISTEOF
    sed -i '' "s|__APP_DIR__|${APP_DIR}|g" "$PLIST_FILE"
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE" 2>/dev/null
    echo "✓ LaunchAgent installed and started"

elif [ "$OS_TYPE" = "wsl" ]; then
    echo "→ Setting up WSL background service..."
    pkill -f "python.*app.py" 2>/dev/null || true
    nohup "$APP_DIR/.venv/bin/python" "$APP_DIR/app.py" > "$APP_DIR/reclmr.log" 2>&1 &
    echo $! > "$APP_DIR/reclmr.pid"
    echo "✓ reclmr started (PID: $(cat "$APP_DIR/reclmr.pid"))"

else
    # Linux: systemd user service
    echo "→ Setting up systemd user service..."
    sudo loginctl enable-linger $(whoami) 2>/dev/null || true

    SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"
    SERVICE_FILE="$SERVICE_DIR/${SERVICE_NAME}.service"

    cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=reclmr
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=3
# Hardening. NoNewPrivileges also stops sudo inside the web terminal (use SSH for admin work).
NoNewPrivileges=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictRealtime=yes
SystemCallArchitectures=native
MemoryMax=8G
TasksMax=2048

[Install]
WantedBy=default.target
SVCEOF

    systemctl --user daemon-reload
    systemctl --user enable reclmr
    systemctl --user restart reclmr
    echo "✓ Service installed and started"
fi

# ─── Start reclmr (app + Tailscale funnel together) ─────────────
echo ""
echo "→ Starting reclmr..."
chmod +x "$APP_DIR/reclmr"

# Put `reclmr` on PATH (~/.local/bin) so `reclmr update` / `reclmr status`
# work from any directory. Most distros already include ~/.local/bin in PATH.
mkdir -p "$HOME/.local/bin"
ln -sf "$APP_DIR/reclmr" "$HOME/.local/bin/reclmr"
echo "✓ 'reclmr' command installed to ~/.local/bin (reclmr update, status, qr, …)"

# The reclmr wrapper starts the app and the Tailscale funnel together
# (no third-party relays). A non-root user may need `sudo tailscale funnel`.
"$APP_DIR/reclmr" start || echo "  (the tunnel did not start: the app itself is running. See docs/SETUP.md to set up phone access)"

# Get the funnel URL (can take a few seconds to appear)
TUNNEL_URL=""
for _ in 1 2 3 4 5; do
    TUNNEL_URL=$(tailscale funnel status 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.tail[a-z0-9-]+\.ts\.net' | head -1)
    [ -n "$TUNNEL_URL" ] && break
    sleep 2
done

if [ -n "$TUNNEL_URL" ]; then
    echo "✓ Funnel active: $TUNNEL_URL"
    ACCESS_URL="$TUNNEL_URL"
else
    echo "⚠ Funnel not active yet. Local access only:"
    ACCESS_URL="http://localhost:${PORT}"
    echo "  $ACCESS_URL"
    echo "  To start the tunnel: sudo tailscale funnel ${PORT}"
fi

# ─── Done ───────────────────────────────────────────────────────
PIN=$(grep "^RECLMR_PIN=" .env 2>/dev/null | tail -n1 | cut -d= -f2 || echo "")
echo ""
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✓ reclmr installed!                       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
MUSIC=$(grep "^RECLMR_MUSIC_DIR=" .env 2>/dev/null | tail -n1 | cut -d= -f2)
echo "   Open:       http://localhost:${PORT}"
echo "   Passcode:   ${PIN:-set in .env}   (kept in ${APP_DIR}/.env)"
echo "   Music:      ${MUSIC:-~/Music}   (put songs there: no other software needed)"
if [ -n "$TUNNEL_URL" ]; then
    echo "   On your phone: $TUNNEL_URL"
else
    echo "   On your phone: not set up yet. It takes two minutes with Tailscale: see docs/SETUP.md"
fi
echo ""

# QR code (phone)
if [ -n "$TUNNEL_URL" ] && command -v qrencode &>/dev/null; then
    echo "   Scan with your phone camera:"
    echo ""
    qrencode -t ANSIUTF8 "$TUNNEL_URL" 2>/dev/null || qrencode -t ANSI "$TUNNEL_URL" 2>/dev/null
    echo ""
    echo "   Then 'Add to Home Screen' for an app-like icon (iPhone: Safari Share menu. Android: Chrome menu)."
    echo ""
fi

echo "Manage reclmr:"
echo "  ./reclmr status   — check what's running"
echo "  ./reclmr qr       — show current tunnel URL + QR code"
echo "  ./reclmr restart  — restart app + tunnel (new QR if tunnel changed)"
echo ""
echo "System service:"
if [ "$OS_TYPE" = "macos" ]; then
    echo "  launchctl list | grep reclmr      # status"
    echo "  launchctl unload $PLIST_FILE       # stop"
    echo "  launchctl load $PLIST_FILE         # start"
elif [ "$OS_TYPE" = "wsl" ]; then
    echo "  ./reclmr restart                  # restart everything"
else
    echo "  systemctl --user status reclmr    # status"
    echo "  systemctl --user restart reclmr   # restart"
    echo "  systemctl --user stop reclmr      # stop"
fi
echo ""
echo "Uninstall: ./uninstall.sh"
echo "Edit settings: nano ${APP_DIR}/.env"