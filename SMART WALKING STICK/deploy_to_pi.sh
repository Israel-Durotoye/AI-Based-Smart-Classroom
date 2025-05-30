#!/bin/bash

# Configuration
PI_USER="pi"  # Change this to your Raspberry Pi username
PI_HOST="192.168.137.154"  # Change this to your Pi's hostname or IP
PI_PATH="/home/pi/companion-stick"  # Destination path on the Pi

# Function to check command success
check_error() {
    if [ $? -ne 0 ]; then
        echo "Error: $1"
        exit 1
    fi
}

# Function to setup UART and A9G module
setup_uart() {
    echo "Setting up UART and A9G module..."
    
    # Copy UART configuration script
    scp configure_uart.sh $PI_USER@$PI_HOST:$PI_PATH/
    check_error "Failed to copy UART configuration script"
    
    # Make script executable and run it
    ssh $PI_USER@$PI_HOST "cd $PI_PATH && chmod +x configure_uart.sh && sudo ./configure_uart.sh"
    check_error "Failed to configure UART"
    
    # Install required packages for serial communication
    ssh $PI_USER@$PI_HOST "sudo apt-get update && sudo apt-get install -y python3-serial minicom"
    check_error "Failed to install serial packages"
    
    # Test serial ports
    ssh $PI_USER@$PI_HOST "ls -l /dev/serial* || true"
}

# Test SSH connection first
echo "Testing SSH connection..."
ssh -q $PI_USER@$PI_HOST "exit"
check_error "Cannot connect to Raspberry Pi. Please check your SSH connection and Pi's IP address."

echo "Preparing to deploy scripts to Raspberry Pi..."

# Create deployment directory
ssh $PI_USER@$PI_HOST "mkdir -p $PI_PATH"
check_error "Failed to create deployment directory"

# Copy all necessary files
echo "Copying files to Raspberry Pi..."
scp \
    configure_uart.sh \
    a9g_module.py \
    firebase_alerts.py \
    camera_monitor.py \
    sensor_monitor.py \
    test_components.py \
    requirements_pi.txt \
    walking-stick-app-firebase-adminsdk-fbsvc-3c09a7dcb7.json \
    $PI_USER@$PI_HOST:$PI_PATH/
check_error "Failed to copy files"

# Setup Python virtual environment and install requirements
echo "Setting up Python virtual environment..."
ssh $PI_USER@$PI_HOST "cd $PI_PATH && \
    sudo apt-get update && \
    sudo apt-get install -y python3-venv python3-pip libatlas-base-dev && \
    python3 -m venv venv && \
    source venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements_pi.txt"
check_error "Failed to setup Python environment"

# Setup UART and A9G module
setup_uart

# Install Python requirements
echo "Installing Python requirements..."
ssh $PI_USER@$PI_HOST "cd $PI_PATH && python3 -m pip install -r requirements_pi.txt"
check_error "Failed to install Python requirements"

echo "Testing A9G module initialization..."
ssh $PI_USER@$PI_HOST "cd $PI_PATH && python3 -c 'from a9g_module import A9GModule; module = A9GModule(); print(\"Testing module...\"); module.init_module(); module.cleanup()'"

# Create the destination directory if it doesn't exist
ssh $PI_USER@$PI_HOST "mkdir -p $PI_PATH"
check_error "Failed to create destination directory"

# Copy files to the Pi
echo "Copying files to Raspberry Pi..."
scp sensor_monitor4.py \
    test_ultrasonic.py \
    test_mpu6050.py \
    test_light_sensor.py \
    test_dht11.py \
    firebase_alerts.py \
    a9g_module.py \
    camera_monitor.py \
    requirements_pi.txt \
    google-services.json \
    walking-stick-app-firebase-adminsdk-fbsvc-c9db4d30a3.json \
    $PI_USER@$PI_HOST:$PI_PATH/

# Copy Vosk model
echo "Copying Vosk model..."
scp -r vosk-model/ $PI_USER@$PI_HOST:$PI_PATH/
check_error "Failed to copy files"

# Set up the environment on the Pi
echo "Setting up environment on Raspberry Pi..."
ssh $PI_USER@$PI_HOST "cd $PI_PATH && \
    # Install system dependencies
    sudo apt-get update && \
    sudo apt-get install -y \
        python3-pip \
        python3-dev \
        python3-picamera2 \
        python3-libcamera \
        python3-opencv \
        portaudio19-dev \
        python3-rpi.gpio \
        python3-smbus \
        i2c-tools \
        libatlas-base-dev \
        python3-venv && \
    # Create and activate virtual environment
    python3 -m venv venv && \
    source venv/bin/activate && \
    # Install Python requirements
    pip3 install -r requirements_pi.txt && \
    # Set up GPIO permissions
    if ! groups | grep -q 'gpio'; then \
        sudo usermod -a -G gpio \$USER; \
        echo 'User added to gpio group'; \
    fi && \
    # Add udev rules for GPIO access
    if [ ! -f /etc/udev/rules.d/99-gpio.rules ]; then \
        echo 'SUBSYSTEM==\"bcm2835-gpiomem\", GROUP=\"gpio\", MODE=\"0660\"' | sudo tee /etc/udev/rules.d/99-gpio.rules && \
        echo 'SUBSYSTEM==\"gpio\", GROUP=\"gpio\", MODE=\"0660\"' | sudo tee -a /etc/udev/rules.d/99-gpio.rules && \
        sudo udevadm control --reload-rules && sudo udevadm trigger; \
    fi"
check_error "Failed to set up environment on Raspberry Pi"

echo "Deployment complete!"
echo "Before running the system, please:"
echo "1. Connect the sensors according to the following pins:"
echo "   - DHT11: DATA → GPIO4"
echo "   - Ultrasonic: TRIG → GPIO23, ECHO → GPIO24"
echo "   - MPU6050: SDA → GPIO2, SCL → GPIO3"
echo "   - LDR: Signal → GPIO17"
echo "   - Button: Signal → GPIO27"
echo "2. Reboot your Pi for all permission changes to take effect"
echo "3. To run the companion stick system:"
echo "   cd $PI_PATH && source venv/bin/activate && python3 sensor_monitor4.py"
