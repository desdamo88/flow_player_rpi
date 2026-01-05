#!/bin/bash
#
# Flow Player - RPi Image Builder
# Creates a ready-to-flash Raspberry Pi image with Flow Player pre-installed
#
# Requirements:
#   - Raspberry Pi OS Lite (Bookworm) base image
#   - Docker (for pi-gen) OR physical RPi for direct setup
#   - ~16GB free disk space
#
# Method 1: Clone from configured SD card (simplest)
# Method 2: Use pi-gen to build custom image
# Method 3: Use Raspberry Pi Imager with cloud-init
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_DIR}/build"
IMAGE_NAME="flow-player-rpi"
VERSION="1.0.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "============================================"
echo "   Flow Player - RPi Image Builder"
echo "============================================"
echo -e "${NC}"

show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  clone     - Clone from a running RPi SD card (requires SSH access)"
    echo "  pigen     - Build using pi-gen (requires Docker)"
    echo "  cloudinit - Generate cloud-init config for RPi Imager"
    echo "  help      - Show this help"
    echo ""
}

# Method 1: Clone from SD card
clone_from_sd() {
    echo -e "${GREEN}[Clone Method] Creating image from SD card...${NC}"

    read -p "Enter RPi IP address: " RPI_IP
    read -p "Enter username (default: pi): " RPI_USER
    RPI_USER="${RPI_USER:-pi}"

    echo "This will create a compressed image from the RPi's SD card."
    echo "Make sure the RPi has enough free space for temporary files."

    mkdir -p "${BUILD_DIR}"

    # Create image on RPi and transfer
    echo "Creating image on RPi (this may take 30+ minutes)..."
    ssh "${RPI_USER}@${RPI_IP}" "sudo dd if=/dev/mmcblk0 bs=4M status=progress | gzip" > "${BUILD_DIR}/${IMAGE_NAME}-${VERSION}.img.gz"

    echo -e "${GREEN}Image created: ${BUILD_DIR}/${IMAGE_NAME}-${VERSION}.img.gz${NC}"
    echo ""
    echo "To flash:"
    echo "  gunzip -c ${BUILD_DIR}/${IMAGE_NAME}-${VERSION}.img.gz | sudo dd of=/dev/sdX bs=4M status=progress"
}

# Method 2: Pi-gen (Docker)
build_pigen() {
    echo -e "${GREEN}[Pi-gen Method] Building custom image...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is required for pi-gen builds${NC}"
        exit 1
    fi

    mkdir -p "${BUILD_DIR}/pi-gen"
    cd "${BUILD_DIR}/pi-gen"

    # Clone pi-gen if not exists
    if [ ! -d "pi-gen" ]; then
        git clone https://github.com/RPi-Distro/pi-gen.git
    fi

    cd pi-gen

    # Create config
    cat > config << EOF
IMG_NAME='flow-player'
RELEASE=bookworm
DEPLOY_ZIP=1
LOCALE_DEFAULT=fr_FR.UTF-8
TARGET_HOSTNAME=flowplayer
KEYBOARD_KEYMAP=fr
KEYBOARD_LAYOUT="French"
TIMEZONE_DEFAULT=Europe/Paris
FIRST_USER_NAME=pi
FIRST_USER_PASS=flowplayer
ENABLE_SSH=1
EOF

    # Create custom stage for Flow Player
    mkdir -p stage-flow-player/00-install-flow-player/files

    # Copy project files
    cp -r "${PROJECT_DIR}"/* stage-flow-player/00-install-flow-player/files/

    # Create install script for stage
    cat > stage-flow-player/00-install-flow-player/00-run.sh << 'STAGE_SCRIPT'
#!/bin/bash -e

on_chroot << CHROOT
# Install dependencies
apt-get update
apt-get install -y python3-venv python3-pip mpv libmpv-dev avahi-daemon

# Create flow-player directory
mkdir -p /opt/flow-player
cp -r /tmp/flow-player-files/* /opt/flow-player/
chown -R 1000:1000 /opt/flow-player

# Create venv and install requirements
cd /opt/flow-player
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Install systemd service
cp /opt/flow-player/systemd/flow-player.service /etc/systemd/system/
systemctl enable flow-player

# Configure Avahi
cp /opt/flow-player/systemd/flow-player.service.avahi /etc/avahi/services/flow-player.service 2>/dev/null || true
systemctl enable avahi-daemon

# Configure GPU memory
echo "gpu_mem=256" >> /boot/config.txt

# Add user to groups
usermod -a -G video,audio,dialout,gpio pi
CHROOT
STAGE_SCRIPT

    chmod +x stage-flow-player/00-install-flow-player/00-run.sh

    # Copy files to stage
    cp -r "${PROJECT_DIR}"/* stage-flow-player/00-install-flow-player/files/

    # Skip stages we don't need
    touch stage3/SKIP stage4/SKIP stage5/SKIP
    touch stage4/SKIP_IMAGES stage5/SKIP_IMAGES

    # Build
    echo "Building image (this takes 30-60 minutes)..."
    ./build-docker.sh

    # Copy output
    cp deploy/*.zip "${BUILD_DIR}/"

    echo -e "${GREEN}Image built: ${BUILD_DIR}/flow-player-*.zip${NC}"
}

# Method 3: Cloud-init for RPi Imager
generate_cloudinit() {
    echo -e "${GREEN}[Cloud-init Method] Generating configuration...${NC}"

    mkdir -p "${BUILD_DIR}/cloud-init"

    # user-data (cloud-init config)
    cat > "${BUILD_DIR}/cloud-init/user-data" << 'EOF'
#cloud-config

hostname: flowplayer
manage_etc_hosts: true

users:
  - name: pi
    groups: [adm, dialout, cdrom, sudo, audio, video, plugdev, games, users, input, render, netdev, gpio, i2c, spi]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    # Password: flowplayer (change this!)
    passwd: $6$rounds=4096$xyz$hashed_password_here

package_update: true
package_upgrade: true

packages:
  - python3-venv
  - python3-pip
  - mpv
  - libmpv-dev
  - git
  - avahi-daemon
  - avahi-utils

runcmd:
  # Clone and install Flow Player
  - git clone https://github.com/desdamo88/flow_player_rpi.git /opt/flow-player
  - chown -R pi:pi /opt/flow-player
  - cd /opt/flow-player && sudo -u pi python3 -m venv venv
  - cd /opt/flow-player && sudo -u pi ./venv/bin/pip install -r requirements.txt
  - cp /opt/flow-player/systemd/flow-player.service /etc/systemd/system/
  - systemctl daemon-reload
  - systemctl enable flow-player
  - systemctl start flow-player
  # Configure GPU
  - echo "gpu_mem=256" >> /boot/config.txt
  # Avahi
  - cp /opt/flow-player/systemd/flow-player.service.avahi /etc/avahi/services/ 2>/dev/null || true
  - systemctl restart avahi-daemon

final_message: |
  Flow Player installation complete!
  Access at: http://flowplayer.local:5000
EOF

    # network-config
    cat > "${BUILD_DIR}/cloud-init/network-config" << 'EOF'
version: 2
ethernets:
  eth0:
    dhcp4: true
    optional: true
wifis:
  wlan0:
    dhcp4: true
    optional: true
    # Uncomment and configure for WiFi:
    # access-points:
    #   "YourNetworkName":
    #     password: "YourPassword"
EOF

    echo -e "${GREEN}Cloud-init files generated in: ${BUILD_DIR}/cloud-init/${NC}"
    echo ""
    echo "To use with Raspberry Pi Imager:"
    echo "1. Flash Raspberry Pi OS Lite (64-bit) to SD card"
    echo "2. Copy user-data and network-config to boot partition"
    echo "3. Boot the RPi - Flow Player will auto-install"
    echo ""
    echo "Or use the quick setup script below on a fresh RPi:"

    # Also create a simple curl-install script
    cat > "${BUILD_DIR}/cloud-init/quick-install.sh" << 'EOF'
#!/bin/bash
# Quick install script - run this on a fresh Raspberry Pi OS
# curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh | sudo bash

set -e

echo "Installing Flow Player..."

# Update and install deps
apt update && apt install -y python3-venv python3-pip mpv libmpv-dev git avahi-daemon

# Clone repo
git clone https://github.com/desdamo88/flow_player_rpi.git /opt/flow-player
chown -R pi:pi /opt/flow-player

# Setup venv
cd /opt/flow-player
sudo -u pi python3 -m venv venv
sudo -u pi ./venv/bin/pip install -r requirements.txt

# Install service
cp systemd/flow-player.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable flow-player
systemctl start flow-player

# Avahi
cp systemd/flow-player.service.avahi /etc/avahi/services/ 2>/dev/null || true
systemctl restart avahi-daemon

# GPU config
grep -q "gpu_mem" /boot/config.txt || echo "gpu_mem=256" >> /boot/config.txt

echo ""
echo "Flow Player installed!"
echo "Access at: http://$(hostname).local:5000"
echo "Reboot recommended: sudo reboot"
EOF

    chmod +x "${BUILD_DIR}/cloud-init/quick-install.sh"

    echo ""
    echo -e "${YELLOW}Quick install (on fresh RPi):${NC}"
    echo "curl -sSL https://raw.githubusercontent.com/desdamo88/flow_player_rpi/main/scripts/quick-install.sh | sudo bash"
}

# Main
case "${1:-help}" in
    clone)
        clone_from_sd
        ;;
    pigen)
        build_pigen
        ;;
    cloudinit)
        generate_cloudinit
        ;;
    help|*)
        show_usage
        ;;
esac
