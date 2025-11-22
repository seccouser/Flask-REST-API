#!/bin/bash
#
# Installation script for Flask REST API on Radxa Rock 5b / Armbian Linux
#

set -e

echo "============================================"
echo "Flask REST API Installation Script"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

# Update system
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install Python and pip if not installed
echo "Installing Python and dependencies..."
apt-get install -y python3 python3-pip python3-dev git

# Install system dependencies for evdev
echo "Installing evdev system dependencies..."
if ! apt-get install -y gcc linux-headers-$(uname -r); then
    echo "Warning: Could not install linux-headers. Keyboard emulation may not work."
fi

# Create installation directory
INSTALL_DIR="/opt/Flask-REST-API"
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Copy files if running from a different directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying application files from $SCRIPT_DIR..."
    cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/requirements.txt "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/flask-api.service /etc/systemd/system/ 2>/dev/null || true
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create uploads directory
echo "Creating uploads directory..."
mkdir -p $INSTALL_DIR/uploads
chmod 755 $INSTALL_DIR/uploads

# Setup uinput permissions for keyboard emulation
echo "Setting up uinput permissions for keyboard emulation..."
modprobe uinput || true
echo "uinput" >> /etc/modules || true

# Create udev rule for uinput
cat > /etc/udev/rules.d/99-uinput.rules << 'EOF'
KERNEL=="uinput", MODE="0666", GROUP="input"
EOF

udevadm control --reload-rules
udevadm trigger

# Add current user to input group (if not root)
if [ -n "$SUDO_USER" ]; then
    echo "Adding user $SUDO_USER to input group..."
    usermod -a -G input $SUDO_USER
fi

# Install systemd service
if [ -f "/etc/systemd/system/flask-api.service" ]; then
    echo "Installing systemd service..."
    systemctl daemon-reload
    systemctl enable flask-api.service
    
    echo ""
    echo "Service installed! You can manage it with:"
    echo "  sudo systemctl start flask-api"
    echo "  sudo systemctl stop flask-api"
    echo "  sudo systemctl status flask-api"
    echo "  sudo systemctl restart flask-api"
    echo ""
fi

# Test installation
echo "Testing Flask installation..."
python3 -c "import flask; print(f'Flask version: {flask.__version__}')"

echo "Testing evdev installation..."
python3 -c "import evdev; print('evdev installed successfully')" 2>/dev/null && EVDEV_OK=1 || EVDEV_OK=0

if [ $EVDEV_OK -eq 0 ]; then
    echo "Warning: evdev not installed properly. Keyboard emulation may not work."
    echo "Try: pip3 install --upgrade python-evdev"
fi

echo ""
echo "============================================"
echo "Installation completed!"
echo "============================================"
echo ""
echo "To start the server manually:"
echo "  cd $INSTALL_DIR"
echo "  sudo python3 app.py"
echo ""
echo "Or use the systemd service:"
echo "  sudo systemctl start flask-api"
echo ""
echo "The API will be available at: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Note: For keyboard emulation to work, you may need to:"
echo "  1. Logout and login again (to apply group membership)"
echo "  2. Or run the server as root"
echo ""
