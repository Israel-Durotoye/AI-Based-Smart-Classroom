#!/bin/bash

echo "Configuring UART for A9G module..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Disable serial console
raspi-config nonint do_serial 1

# Enable UART hardware
echo "Enabling UART in config.txt..."
if ! grep -q "enable_uart=1" /boot/config.txt; then
    echo "enable_uart=1" >> /boot/config.txt
fi

# Disable Bluetooth to free up UART
if ! grep -q "dtoverlay=disable-bt" /boot/config.txt; then
    echo "dtoverlay=disable-bt" >> /boot/config.txt
fi

# Set permissions for serial devices
for device in /dev/serial0 /dev/ttyAMA0 /dev/ttyS0; do
    if [ -e "$device" ]; then
        chmod 666 "$device"
        echo "Set permissions for $device"
    fi
done

# Add user to dialout group
usermod -a -G dialout pi

echo "UART configuration complete. Please reboot for changes to take effect."
echo "After reboot, verify serial ports with: ls -l /dev/serial*"
