#!/bin/bash
#
# Flow Player - Installation Script
# For Raspberry Pi 5 running Raspberry Pi OS (Bookworm)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/flow-player"
SERVICE_USER="pi"

echo -e "${GREEN}"
echo "=========================================="
echo "       Flow Player Installation"
echo "=========================================="
echo -e "${NC}"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (sudo)${NC}"
   exit 1
fi

# Check for Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}[1/6] Updating system packages...${NC}"
apt update
apt upgrade -y

echo -e "${GREEN}[2/7] Installing system dependencies...${NC}"
apt install -y \
    python3-venv \
    python3-pip \
    python3-dev \
    mpv \
    libmpv-dev \
    git \
    libgl1-mesa-dev \
    libegl1-mesa-dev \
    libgbm-dev \
    avahi-daemon \
    avahi-utils

echo -e "${GREEN}[3/6] Creating installation directory...${NC}"
mkdir -p ${INSTALL_DIR}
mkdir -p ${INSTALL_DIR}/shows
mkdir -p ${INSTALL_DIR}/config
mkdir -p ${INSTALL_DIR}/logs

# Copy files if running from source directory
if [ -f "$(dirname "$0")/requirements.txt" ]; then
    echo -e "${GREEN}[3.5/6] Copying source files...${NC}"
    cp -r "$(dirname "$0")"/* ${INSTALL_DIR}/
fi

chown -R ${SERVICE_USER}:${SERVICE_USER} ${INSTALL_DIR}

echo -e "${GREEN}[4/6] Creating Python virtual environment...${NC}"
cd ${INSTALL_DIR}
sudo -u ${SERVICE_USER} python3 -m venv venv
sudo -u ${SERVICE_USER} ${INSTALL_DIR}/venv/bin/pip install --upgrade pip

echo -e "${GREEN}[5/6] Installing Python dependencies...${NC}"
sudo -u ${SERVICE_USER} ${INSTALL_DIR}/venv/bin/pip install -r requirements.txt

echo -e "${GREEN}[6/6] Installing systemd service...${NC}"
cp ${INSTALL_DIR}/systemd/flow-player.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable flow-player

# Create USB automount rules
echo -e "${GREEN}Setting up USB automount...${NC}"
cat > /etc/udev/rules.d/99-flow-player-usb.rules << 'EOF'
# Auto-mount USB drives for Flow Player
SUBSYSTEM=="block", KERNEL=="sd[a-z]1", ACTION=="add", RUN+="/bin/mkdir -p /media/usb", RUN+="/bin/mount -o uid=1000,gid=1000 /dev/%k /media/usb"
SUBSYSTEM=="block", KERNEL=="sd[a-z]1", ACTION=="remove", RUN+="/bin/umount -l /media/usb"

# USB DMX devices permissions
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0666"
EOF

udevadm control --reload-rules

# Configure GPU memory (for video playback)
echo -e "${GREEN}Configuring GPU memory...${NC}"
if ! grep -q "gpu_mem" /boot/config.txt 2>/dev/null; then
    echo "gpu_mem=256" >> /boot/config.txt
fi

# Add user to required groups
usermod -a -G video,audio,dialout,gpio ${SERVICE_USER}

# Setup hostname and Avahi
echo -e "${GREEN}[7/7] Setting up network discovery (mDNS)...${NC}"
DEFAULT_HOSTNAME="flowplayer"
read -p "Enter hostname for this device [${DEFAULT_HOSTNAME}]: " CUSTOM_HOSTNAME
HOSTNAME="${CUSTOM_HOSTNAME:-$DEFAULT_HOSTNAME}"

# Validate and set hostname
if [[ "$HOSTNAME" =~ ^[a-zA-Z][a-zA-Z0-9-]*$ ]]; then
    hostnamectl set-hostname "$HOSTNAME"
    sed -i "s/127.0.1.1.*/127.0.1.1\t$HOSTNAME/" /etc/hosts
    if ! grep -q "127.0.1.1" /etc/hosts; then
        echo "127.0.1.1	$HOSTNAME" >> /etc/hosts
    fi

    # Install Avahi service file
    if [ -f "${INSTALL_DIR}/systemd/flow-player.service.avahi" ]; then
        cp "${INSTALL_DIR}/systemd/flow-player.service.avahi" /etc/avahi/services/flow-player.service
    fi

    systemctl restart avahi-daemon
    systemctl enable avahi-daemon

    echo -e "${GREEN}Hostname set to: ${HOSTNAME}${NC}"
    echo -e "${GREEN}Device will be accessible at: ${HOSTNAME}.local${NC}"
else
    echo -e "${YELLOW}Invalid hostname, skipping hostname setup${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "       Installation Complete!"
echo "==========================================${NC}"
echo ""
echo "Flow Player has been installed to: ${INSTALL_DIR}"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start flow-player"
echo "  Stop:    sudo systemctl stop flow-player"
echo "  Status:  sudo systemctl status flow-player"
echo "  Logs:    journalctl -u flow-player -f"
echo ""
echo "Web interface will be available at:"
echo "  http://$(hostname -I | awk '{print $1}'):5000"
echo "  http://$(hostname).local:5000"
echo ""
echo -e "${YELLOW}A reboot is recommended to apply all changes.${NC}"
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
fi
