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

# Try to upgrade, but don't fail if it doesn't work (e.g., mirror sync issues)
echo "Attempting system upgrade (optional, continuing on failure)..."
apt-get upgrade -y || echo "Warning: System upgrade failed, but continuing installation..."

# Install Python and pip if not installed
echo "Installing Python and dependencies..."
apt-get install -y python3 python3-pip python3-dev python3-venv python3-full git

# Install system dependencies for evdev
echo "Installing evdev system dependencies..."
if ! apt-get install -y gcc linux-headers-$(uname -r); then
    echo "Warning: Could not install linux-headers. Keyboard emulation may not work."
fi

# Create installation directory
INSTALL_DIR="/opt/Flask-REST-API"
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR

# Copy files if running from a different directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: $SCRIPT_DIR"
echo "Installation directory: $INSTALL_DIR"

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying application files from $SCRIPT_DIR to $INSTALL_DIR..."
    
    # Copy Python files
    if ! cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null; then
        echo "Warning: Could not copy Python files"
    fi
    
    # Copy requirements.txt (critical file)
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
        echo "✓ Copied requirements.txt"
    else
        echo "Error: requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi
    
    # Copy service file
    if [ -f "$SCRIPT_DIR/flask-api.service" ]; then
        cp "$SCRIPT_DIR/flask-api.service" /etc/systemd/system/
        echo "✓ Copied flask-api.service"
    else
        echo "Warning: flask-api.service not found"
    fi
fi

# Change to installation directory
cd $INSTALL_DIR

# Create and activate virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv

# Install Python dependencies in virtual environment
echo "Installing Python dependencies in virtual environment..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

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
./venv/bin/python3 -c "import flask; print(f'Flask version: {flask.__version__}')"

echo "Testing evdev installation..."
./venv/bin/python3 -c "import evdev; print('evdev installed successfully')" 2>/dev/null && EVDEV_OK=1 || EVDEV_OK=0

if [ $EVDEV_OK -eq 0 ]; then
    echo "Warning: evdev not installed properly. Keyboard emulation may not work."
    echo "Try: ./venv/bin/pip install --upgrade python-evdev"
fi

echo ""
echo "============================================"
echo "Installation completed!"
echo "============================================"
echo ""
echo "To start the server manually:"
echo "  cd $INSTALL_DIR"
echo "  sudo ./venv/bin/python3 app.py"
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
