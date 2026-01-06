#!/bin/bash
#
# Flow Player - Quick Install Script for Raspberry Pi 5
# Run on a fresh Raspberry Pi OS Lite (Bookworm 64-bit)
#
# Usage (method 1 - direct):
#   curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh | sudo bash
#
# Usage (method 2 - safer, download first):
#   curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh -o /tmp/install.sh
#   sudo bash /tmp/install.sh
#

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Print banner
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Flow Player - Quick Install v1.0       ║${NC}"
echo -e "${GREEN}║     For Raspberry Pi 5                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR] This script must be run as root (use sudo)${NC}"
   echo "Usage: sudo bash $0"
   exit 1
fi

# Detect user (handle both direct root and sudo)
if [ -n "$SUDO_USER" ]; then
    INSTALL_USER="$SUDO_USER"
elif id "pi" &>/dev/null; then
    INSTALL_USER="pi"
elif id "flow" &>/dev/null; then
    INSTALL_USER="flow"
else
    INSTALL_USER=$(who | head -1 | awk '{print $1}')
fi

INSTALL_DIR="/opt/flow-player"
REPO_URL="https://github.com/desdamo88/flow_player_rpi.git"

echo -e "${BLUE}Installation user: ${INSTALL_USER}${NC}"
echo -e "${BLUE}Install directory: ${INSTALL_DIR}${NC}"
echo ""

# Check internet connectivity
echo -e "${GREEN}[0/7] Checking internet connectivity...${NC}"
if ! ping -c 1 github.com &>/dev/null; then
    echo -e "${RED}[ERROR] No internet connection. Please check your network.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Internet OK${NC}"

echo -e "${GREEN}[1/7] Updating system packages...${NC}"
apt update || { echo -e "${RED}apt update failed${NC}"; exit 1; }
apt upgrade -y || { echo -e "${YELLOW}apt upgrade had warnings (continuing)${NC}"; }

echo -e "${GREEN}[2/7] Installing system dependencies...${NC}"
apt install -y \
    python3-venv \
    python3-pip \
    python3-dev \
    mpv \
    libmpv-dev \
    git \
    avahi-daemon \
    avahi-utils \
    || { echo -e "${RED}Failed to install dependencies${NC}"; exit 1; }
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

echo -e "${GREEN}[3/7] Cloning Flow Player repository...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${YELLOW}  Existing installation found, updating...${NC}"
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
else
    rm -rf "$INSTALL_DIR" 2>/dev/null || true
    git clone "$REPO_URL" "$INSTALL_DIR" || { echo -e "${RED}Failed to clone repository${NC}"; exit 1; }
fi
echo -e "${GREEN}  ✓ Repository cloned${NC}"

chown -R "${INSTALL_USER}:${INSTALL_USER}" "$INSTALL_DIR"

echo -e "${GREEN}[4/7] Setting up Python virtual environment...${NC}"
cd "$INSTALL_DIR"
sudo -u "$INSTALL_USER" python3 -m venv venv || { echo -e "${RED}Failed to create venv${NC}"; exit 1; }
sudo -u "$INSTALL_USER" ./venv/bin/pip install --upgrade pip -q
echo -e "${GREEN}  ✓ Virtual environment created${NC}"

echo -e "${GREEN}[5/7] Installing Python dependencies...${NC}"
sudo -u "$INSTALL_USER" ./venv/bin/pip install -r requirements.txt -q || { echo -e "${RED}Failed to install Python packages${NC}"; exit 1; }
echo -e "${GREEN}  ✓ Python packages installed${NC}"

echo -e "${GREEN}[6/7] Installing systemd service...${NC}"
cp systemd/flow-player.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable flow-player
echo -e "${GREEN}  ✓ Service installed${NC}"

# Avahi service for mDNS discovery
if [ -f "systemd/flow-player.service.avahi" ]; then
    mkdir -p /etc/avahi/services
    cp systemd/flow-player.service.avahi /etc/avahi/services/flow-player.service
fi
systemctl enable avahi-daemon 2>/dev/null || true
systemctl restart avahi-daemon 2>/dev/null || true

echo -e "${GREEN}[7/7] Configuring system...${NC}"

# GPU memory for smooth video playback
if [ -f /boot/config.txt ] && ! grep -q "gpu_mem" /boot/config.txt; then
    echo "gpu_mem=256" >> /boot/config.txt
    echo -e "${GREEN}  ✓ GPU memory configured${NC}"
fi

# RPi5 uses /boot/firmware/config.txt
if [ -f /boot/firmware/config.txt ] && ! grep -q "gpu_mem" /boot/firmware/config.txt; then
    echo "gpu_mem=256" >> /boot/firmware/config.txt
    echo -e "${GREEN}  ✓ GPU memory configured${NC}"
fi

# User groups for hardware access
usermod -a -G video,audio,dialout,gpio "$INSTALL_USER" 2>/dev/null || true
echo -e "${GREEN}  ✓ User groups configured${NC}"

# Create required directories
mkdir -p "$INSTALL_DIR/shows"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/logs"
chown -R "${INSTALL_USER}:${INSTALL_USER}" "$INSTALL_DIR"

# Start service
echo ""
echo -e "${BLUE}Starting Flow Player service...${NC}"
systemctl start flow-player

# Wait for service to start
sleep 3

# Check if service is running
if systemctl is-active --quiet flow-player; then
    SERVICE_STATUS="${GREEN}Running${NC}"
else
    SERVICE_STATUS="${YELLOW}Starting (check logs if issues)${NC}"
fi

# Get network info
IP_ADDR=$(hostname -I | awk '{print $1}')
HOSTNAME_VAL=$(hostname)

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Installation Complete!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Service status: ${SERVICE_STATUS}"
echo ""
echo -e "${BLUE}Access the web interface:${NC}"
echo -e "  → http://${IP_ADDR}:5000"
echo -e "  → http://${HOSTNAME_VAL}.local:5000"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  sudo systemctl status flow-player   # Check status"
echo "  sudo systemctl restart flow-player  # Restart"
echo "  sudo journalctl -u flow-player -f   # View logs"
echo ""
echo -e "${YELLOW}⚠ A reboot is recommended to apply all changes.${NC}"
echo ""

# Handle reboot prompt (may not work when piped)
if [ -t 0 ]; then
    read -p "Reboot now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Rebooting..."
        reboot
    fi
else
    echo "Run 'sudo reboot' when ready."
fi
