#!/usr/bin/env bash
# TidalPlan installer for Raspberry Pi / Debian / Ubuntu
# Usage: curl -sSL https://raw.githubusercontent.com/mikekolling1966/tidalplan/main/install.sh | bash

set -e

INSTALL_DIR="/opt/tidalplan"
SERVICE_NAME="tidalplan"
PORT=8081
REPO="https://github.com/mikekolling1966/tidalplan.git"
PYTHON="python3"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         TidalPlan Installer              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── check we are root ──────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo bash, or pipe through sudo bash)"
  exit 1
fi

# ── dependencies ───────────────────────────────────────────────────────────
echo "► Updating package list..."
apt-get update -qq

echo "► Installing system dependencies..."
apt-get install -y -qq git python3 python3-pip python3-venv 2>&1 | tail -3

# ── clone / update repo ────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "► Updating existing installation in $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "► Cloning TidalPlan to $INSTALL_DIR ..."
  git clone "$REPO" "$INSTALL_DIR"
fi

# ── python virtual environment ─────────────────────────────────────────────
echo "► Creating Python virtual environment..."
$PYTHON -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
echo "  ✓ Dependencies installed"

# ── .env file ─────────────────────────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo ""
  echo "► UKHO Admiralty API key setup"
  echo "  Register free at: https://admiraltyapi.portal.azure.com/"
  echo "  (Discovery tier — free, 10,000 req/month)"
  echo ""
  read -rp "  Enter your UKHO API key (or press Enter to skip): " UKHO_KEY
  echo "UKHO_API_KEY=${UKHO_KEY}" > "$ENV_FILE"
  echo "  ✓ .env created"
else
  echo "► .env already exists — skipping key setup"
fi

# ── ensure data directory exists ───────────────────────────────────────────
mkdir -p "$INSTALL_DIR/data"

# ── systemd service ────────────────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "► Installing systemd service..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=TidalPlan — tidal departure window planner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python start.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
# ── get the Pi's IP ────────────────────────────────────────────────────────
PI_IP=$(hostname -I | awk '{print $1}')

echo "╔══════════════════════════════════════════╗"
echo "║        Installation complete! ✓          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  TidalPlan is running at:"
echo ""
echo "    http://${PI_IP}:${PORT}"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status $SERVICE_NAME"
echo "    sudo systemctl restart $SERVICE_NAME"
echo "    sudo journalctl -u $SERVICE_NAME -f"
echo ""
