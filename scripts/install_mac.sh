#!/bin/bash
# RXTERM installer for macOS.
#   curl -fsSL https://raw.githubusercontent.com/itslupichuk/pharma_agent/HEAD/scripts/install_mac.sh | bash
# Installs to ~/RXTERM, puts RXTERM.app on the Desktop (and in ~/Applications), and adds an
# `rxterm` command. Re-run any time to update — your watchlist, cache and .env are kept.
set -euo pipefail

REPO="itslupichuk/pharma_agent"
APP_DIR="$HOME/RXTERM"
AMBER=$'\033[38;5;214m'; DIM=$'\033[2m'; OK=$'\033[32m'; RST=$'\033[0m'
step() { printf "%s▸%s %s\n" "$AMBER" "$RST" "$1"; }

printf "\n%s  RXTERM  %s pharma & biotech trading terminal — installer\n\n" "$AMBER" "$RST"

# 1. Code ───────────────────────────────────────────────────────────────
step "Downloading RXTERM…"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://codeload.github.com/$REPO/zip/HEAD" -o "$TMP/rxterm.zip"
unzip -q "$TMP/rxterm.zip" -d "$TMP"
SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
mkdir -p "$APP_DIR"
# replace the code, keep the virtualenv, your .env and outputs
find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -name ".venv" ! -name ".env" ! -name "out" -exec rm -rf {} +
cp -R "$SRC/." "$APP_DIR/"

# 2. Python environment (uv brings its own Python 3.12 — nothing to install system-wide) ──
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  step "Installing uv (Python manager)…"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
fi
UV="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"
step "Setting up Python 3.12 and dependencies (first run takes ~1 minute)…"
cd "$APP_DIR"
[ -x .venv/bin/python ] || "$UV" venv --quiet --python 3.12 .venv
"$UV" pip install --quiet --python .venv/bin/python -e .
[ -f .env ] || cp .env.example .env

# 3. Launcher script ────────────────────────────────────────────────────
cat > "$APP_DIR/rxterm.command" <<'LAUNCH'
#!/bin/bash
cd "$HOME/RXTERM" && printf '\033]0;RXTERM\007' && exec ./.venv/bin/rxterm "$@"
LAUNCH
chmod +x "$APP_DIR/rxterm.command"
mkdir -p "$HOME/.local/bin"
ln -sf "$APP_DIR/rxterm.command" "$HOME/.local/bin/rxterm"

# 4. RXTERM.app — opens a large dark Terminal window running the terminal ──
step "Creating RXTERM.app…"
APP="$APP_DIR/RXTERM.app"
rm -rf "$APP"
osacompile -o "$APP" <<'APPLESCRIPT'
on run
	tell application "Terminal"
		activate
		set t to do script "clear; exec \"$HOME/RXTERM/rxterm.command\""
		try
			set current settings of t to settings set "Pro"
		end try
		try
			set number of columns of t to 200
			set number of rows of t to 56
		end try
		try
			set custom title of t to "RXTERM"
		end try
	end tell
end run
APPLESCRIPT

# custom icon
if [ -f "$APP_DIR/assets/rxterm_icon.png" ]; then
  ICONSET="$TMP/rxterm.iconset"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$APP_DIR/assets/rxterm_icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2)); sips -z $d $d "$APP_DIR/assets/rxterm_icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns" && touch "$APP"
fi

# Desktop + Applications copies (aliases break across reinstalls; small app, so copy)
for dest in "$HOME/Desktop" "$HOME/Applications"; do
  mkdir -p "$dest"
  rm -rf "$dest/RXTERM.app"
  cp -R "$APP" "$dest/RXTERM.app"
done
xattr -dr com.apple.quarantine "$HOME/Desktop/RXTERM.app" "$HOME/Applications/RXTERM.app" 2>/dev/null || true

# 5. Smoke test ─────────────────────────────────────────────────────────
step "Checking install…"
./.venv/bin/rxterm --version >/dev/null

printf "\n%s✔ RXTERM installed.%s\n\n" "$OK" "$RST"
printf "  Double-click %sRXTERM%s on your Desktop (also in Applications / Launchpad).\n" "$AMBER" "$RST"
printf "  Or type %srxterm%s in Terminal %s(new windows; add ~/.local/bin to PATH if needed)%s.\n" "$AMBER" "$RST" "$DIM" "$RST"
printf "  First launch: macOS may ask to let RXTERM control Terminal — click OK.\n"
printf "  To update later, run this installer again.\n\n"
