#!/bin/bash
#
# Flow Player - Hostname Setup Script
# Sets up mDNS/Avahi for network discovery
#
# Usage: sudo ./setup-hostname.sh [hostname]
# Example: sudo ./setup-hostname.sh flowplayer
#
# This will make the device accessible at flowplayer.local
#

set -e

# Default hostname
DEFAULT_HOSTNAME="flowplayer"
NEW_HOSTNAME="${1:-$DEFAULT_HOSTNAME}"

# Validate hostname
if [[ ! "$NEW_HOSTNAME" =~ ^[a-zA-Z][a-zA-Z0-9-]*$ ]]; then
    echo "Error: Invalid hostname. Must start with a letter and contain only letters, numbers, and hyphens."
    exit 1
fi

echo "=== Flow Player Hostname Setup ==="
echo "Setting hostname to: $NEW_HOSTNAME"
echo "Device will be accessible at: $NEW_HOSTNAME.local"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0 $NEW_HOSTNAME"
    exit 1
fi

# Install avahi if not present
echo "Installing avahi-daemon..."
apt-get update -qq
apt-get install -y avahi-daemon avahi-utils

# Set hostname
echo "Setting hostname..."
hostnamectl set-hostname "$NEW_HOSTNAME"

# Update /etc/hosts
echo "Updating /etc/hosts..."
sed -i "s/127.0.1.1.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
if ! grep -q "127.0.1.1" /etc/hosts; then
    echo "127.0.1.1	$NEW_HOSTNAME" >> /etc/hosts
fi

# Install Avahi service file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AVAHI_SERVICE_SRC="$SCRIPT_DIR/../systemd/flow-player.service.avahi"
AVAHI_SERVICE_DST="/etc/avahi/services/flow-player.service"

if [ -f "$AVAHI_SERVICE_SRC" ]; then
    echo "Installing Avahi service file..."
    cp "$AVAHI_SERVICE_SRC" "$AVAHI_SERVICE_DST"
fi

# Restart avahi
echo "Restarting avahi-daemon..."
systemctl restart avahi-daemon
systemctl enable avahi-daemon

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your device is now accessible at:"
echo "  http://$NEW_HOSTNAME.local:5000"
echo ""
echo "You can also find it with:"
echo "  avahi-browse -art | grep flow-player"
echo ""
echo "To change the hostname later, run:"
echo "  sudo $0 new-hostname"
echo ""
