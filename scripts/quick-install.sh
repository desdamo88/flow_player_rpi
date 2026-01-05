#!/bin/bash
#
# Flow Player - Quick Install Script
# Run on a fresh Raspberry Pi OS Lite (Bookworm)
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh | sudo bash
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "============================================"
echo "   Flow Player - Quick Install"
echo "============================================"
echo -e "${NC}"

# Check root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (sudo)${NC}"
   exit 1
fi

# Detect user (handle both direct root and sudo)
if [ -n "$SUDO_USER" ]; then
    INSTALL_USER="$SUDO_USER"
else
    INSTALL_USER="pi"
fi

INSTALL_DIR="/opt/flow-player"

echo -e "${GREEN}[1/6] Updating system...${NC}"
apt update
apt upgrade -y

echo -e "${GREEN}[2/6] Installing dependencies...${NC}"
apt install -y \
    python3-venv \
    python3-pip \
    python3-dev \
    mpv \
    libmpv-dev \
    git \
    avahi-daemon \
    avahi-utils

echo -e "${GREEN}[3/6] Cloning Flow Player...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone https://github.com/desdamo88/flow_player_rpi.git "$INSTALL_DIR"
fi

chown -R "${INSTALL_USER}:${INSTALL_USER}" "$INSTALL_DIR"

echo -e "${GREEN}[4/6] Setting up Python environment...${NC}"
cd "$INSTALL_DIR"
sudo -u "$INSTALL_USER" python3 -m venv venv
sudo -u "$INSTALL_USER" ./venv/bin/pip install --upgrade pip
sudo -u "$INSTALL_USER" ./venv/bin/pip install -r requirements.txt

echo -e "${GREEN}[5/6] Installing systemd service...${NC}"
cp systemd/flow-player.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable flow-player

# Avahi service
if [ -f "systemd/flow-player.service.avahi" ]; then
    cp systemd/flow-player.service.avahi /etc/avahi/services/flow-player.service
fi
systemctl enable avahi-daemon
systemctl restart avahi-daemon

echo -e "${GREEN}[6/6] Configuring system...${NC}"

# GPU memory
if ! grep -q "gpu_mem" /boot/config.txt 2>/dev/null; then
    echo "gpu_mem=256" >> /boot/config.txt
fi

# User groups
usermod -a -G video,audio,dialout,gpio "$INSTALL_USER" 2>/dev/null || true

# Create required directories
mkdir -p "$INSTALL_DIR/shows"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/logs"
chown -R "${INSTALL_USER}:${INSTALL_USER}" "$INSTALL_DIR"

# Start service
systemctl start flow-player

# Get IP
IP_ADDR=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo ""
echo -e "${GREEN}============================================"
echo "   Installation Complete!"
echo "============================================${NC}"
echo ""
echo "Flow Player is now running!"
echo ""
echo "Access the web interface at:"
echo -e "  ${YELLOW}http://${IP_ADDR}:5000${NC}"
echo -e "  ${YELLOW}http://${HOSTNAME}.local:5000${NC}"
echo ""
echo "Commands:"
echo "  sudo systemctl status flow-player  - Check status"
echo "  sudo systemctl restart flow-player - Restart"
echo "  journalctl -u flow-player -f       - View logs"
echo ""
echo -e "${YELLOW}A reboot is recommended to apply all changes.${NC}"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
fi
