# -*- coding: utf-8 -*-

import serial
import time
import json
import threading
from datetime import datetime
import pynmea2
import math
import random

class A9GModule:
    def __init__(self, serial_port='/dev/ttyS0', baud_rate=115200):
        """Initialize A9G GPS/GSM module."""
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.ser = None
        self.running = True
        self.initialized = False
        
        # SIM card details
        self.module_number = "+2349128892934"
        self.network_registered = False
        self.sim_ready = False
        
        # SIM card details
        self.module_number = "+2349128892934"
        self.network_registered = False
        self.sim_ready = False
        
        # Default location (9.6560° N, 6.5287° E) with metadata
        self.default_location = {
            'latitude': 9.6560,
            'longitude': 6.5287,
            'altitude': 0.0,
            'valid': True,
            'is_default': True,
            'satellites': 0,
            'hdop': 99.99,
            'timestamp': None
        }
        self.last_default_send = 0  # Track last time default location was used
        self.default_send_interval = 60  # Send default location every 60 seconds
        
        # Try different serial ports if the default fails
        possible_ports = ['/dev/ttyS0', '/dev/serial0', '/dev/ttyAMA0', '/dev/ttyUSB0']
        if serial_port not in possible_ports:
            possible_ports.insert(0, serial_port)
            
        # Try to connect to available ports
        for port in possible_ports:
            try:
                print(f"\nTrying to connect to A9G module on {port}...")
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=2,
                    write_timeout=1,
                    rtscts=True,    # Enable hardware flow control
                    dsrdtr=True     # Enable hardware flow control
                )
                
                if self.ser.is_open:
                    print(f"Successfully opened {port}")
                    if self._test_communication():
                        self.serial_port = port
                        print(f"A9G module responding on {port}")
                        if self.init_module():
                            self.initialized = True
                            break
                    
                    print(f"No response from A9G module on {port}")
                    self.ser.close()
                    self.ser = None
                    
            except Exception as e:
                print(f"Error opening {port}: {e}")
                if self.ser:
                    self.ser.close()
                    self.ser = None
        
        if not self.ser:
            print("\nFailed to connect to A9G module!")
            print("Operating in fallback mode with default location")
            self.dev_mode = True
        else:
            self.dev_mode = False

        # Network registration constants
        self.MAX_NETWORK_RETRIES = 10  # Maximum retries for network registration
        self.NETWORK_RETRY_DELAY = 5   # Seconds between retries
        self.MIN_SIGNAL_STRENGTH = 10  # Minimum acceptable signal strength

    def _test_communication(self):
        """Test communication with the A9G module"""
        if not self.ser:
            return False
            
        try:
            # Clear any pending data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Try AT command multiple times
            for _ in range(3):
                self.ser.write(b'AT\r\n')
                time.sleep(1)
                response = self.ser.read_all()
                if b'OK' in response:
                    return True
                time.sleep(0.5)
            
            return False
            
        except Exception as e:
            print(f"Communication test error: {e}")
            return False

    def init_module(self):
        """Initialize the A9G module and configure it."""
        if self.dev_mode:
            return True
            
        try:
            # Initial setup and SIM check commands
            init_commands = [
                ('AT', 1),                 # Test AT
                ('ATZ', 2),                # Reset module
                ('ATE0', 1),               # Disable echo
                ('AT+CPIN?', 2),           # Check SIM status
                ('AT+CSQ', 1),             # Check signal quality
                ('AT+COPS=0', 10),         # Automatic network selection
                ('AT+CREG=1', 1),          # Enable network registration
                ('AT+CMGF=1', 1),          # Set SMS text mode
                ('AT+CSCS="GSM"', 1),      # Set character set
                ('AT+CGPS=1', 2),          # Enable GPS
                ('AT+CGNSPWR=1', 2),       # Power on GNSS
                ('AT+CGNSMOD=1', 1),       # Set automatic GPS operation
            ]
            
            # Execute basic initialization commands
            for cmd, wait_time in init_commands:
                response = self.send_command(cmd, wait_time)
                if not response or ('ERROR' in response and 'OK' not in response):
                    print(f"Failed at command: {cmd}")
                    print(f"Response: {response}")
                    if cmd == 'AT':  # Critical failure if AT fails
                        return False
                    continue
                time.sleep(wait_time)
            
            # Initialize network with enhanced retry logic
            if not self.init_network():
                print("Warning: Network initialization failed")
                # Continue anyway as registration might happen later
            
            print("A9G module initialized successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing A9G module: {e}")
            return False

    def send_command(self, command, wait_time=1):
        """Send AT command to module and get response."""
        if self.dev_mode:
            return "OK"  # Simulate success in dev mode
            
        if not self.ser or not self.ser.is_open:
            print("Error: Serial port not open")
            return None
            
        try:
            # Clear input buffer
            self.ser.reset_input_buffer()
            
            # Send command
            cmd = f"{command}\r\n"
            self.ser.write(cmd.encode())
            
            # Wait for response
            time.sleep(wait_time)
            
            # Read response
            response = ''
            start_time = time.time()
            while (time.time() - start_time) < wait_time:
                if self.ser.in_waiting:
                    new_data = self.ser.read_all()
                    try:
                        response += new_data.decode('utf-8', errors='ignore')
                    except:
                        print(f"Warning: Could not decode response: {new_data}")
                        
                if 'OK' in response or 'ERROR' in response:
                    break
                    
                time.sleep(0.1)
            
            return response.strip()
            
        except Exception as e:
            print(f"Error sending command {command}: {e}")
            return None

    def get_location(self, use_cached=True):
        """Get current GPS location data."""
        if self.dev_mode:
            return self.default_location
            
        try:
            # Check GPS power state
            response = self.send_command('AT+CGPS?')
            if not response or '+CGPS: 1' not in response:
                print("GPS is not enabled, attempting to enable...")
                self.send_command('AT+CGPS=1', wait_time=2)
                time.sleep(2)
            
            # Get location data
            response = self.send_command('AT+CGNSINF', wait_time=2)
            if not response or 'ERROR' in response:
                print("Failed to get GPS data")
                return self._use_default_location()
            
            # Parse CGNSINF response
            # Format: +CGNSINF: <GNSS run status>,<Fix status>,<UTC time>,<Lat>,<Lon>,<Alt>,<Speed>,<Course>
            parts = response.split('+CGNSINF: ')[1].split(',')
            if len(parts) < 6:
                print("Invalid GPS data format")
                return self._use_default_location()
            
            run_status = int(parts[0])
            fix_status = int(parts[1])
            
            if run_status != 1 or fix_status != 1:
                print(f"No GPS fix (Run: {run_status}, Fix: {fix_status})")
                return self._use_default_location()
            
            try:
                lat = float(parts[3])
                lon = float(parts[4])
                alt = float(parts[5]) if parts[5] else 0.0
                
                if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat != 0 or lon != 0):
                    return {
                        'latitude': lat,
                        'longitude': lon,
                        'altitude': alt,
                        'valid': True,
                        'is_default': False,
                        'satellites': int(parts[14]) if len(parts) > 14 else 0,
                        'hdop': float(parts[10]) if len(parts) > 10 else 99.99,
                        'timestamp': datetime.now()
                    }
                
                print("Invalid coordinates received")
                return self._use_default_location()
                
            except (ValueError, IndexError) as e:
                print(f"Error parsing GPS data: {e}")
                return self._use_default_location()
                
        except Exception as e:
            print(f"Error getting location: {e}")
            return self._use_default_location()

    def _use_default_location(self):
        """Return default location if enough time has passed since last use."""
        current_time = time.time()
        if current_time - self.last_default_send >= self.default_send_interval:
            self.last_default_send = current_time
            self.default_location['timestamp'] = datetime.now()
            print("Using default location as fallback")
            return self.default_location
        return None
        
    def cleanup(self):
        """Clean up resources before shutdown."""
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.send_command('AT+CGPS=0')  # Disable GPS
                self.ser.close()
            except:
                pass

    def send_sms(self, phone_number, message):
        """Send SMS using the module."""
        if self.dev_mode:
            print(f"DEV MODE - Simulating SMS to {phone_number}: {message}")
            return True
            
        try:
            # Set SMS text mode
            if not self.send_command('AT+CMGF=1'):
                print("Failed to set SMS text mode")
                return False
            
            time.sleep(1)
            
            # Set recipient number
            cmd = f'AT+CMGS="{phone_number}"'
            response = self.send_command(cmd, wait_time=2)
            if not response or 'ERROR' in response:
                print("Failed to set recipient number")
                return False
            
            # Send message content
            time.sleep(0.5)
            self.ser.write(message.encode())
            self.ser.write(bytes([26]))  # Ctrl+Z to send
            
            # Wait for confirmation
            time.sleep(3)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            
            if '+CMGS:' in response:
                print("SMS sent successfully")
                return True
            else:
                print(f"SMS sending failed. Response: {response}")
                return False
                
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False

    def start_monitoring(self):
        """Start continuous location monitoring."""
        if self.running:
            print("Monitoring already active")
            return
            
        self.running = True
        self._monitor_thread = threading.Thread(target=self._monitor_location)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        print("Location monitoring started")

    def _monitor_location(self):
        """Continuous location monitoring thread."""
        retry_count = 0
        max_retries = 3
        wait_time = 2  # Initial wait time
        
        while self.running:
            try:
                location = self.get_location()
                if location:
                    if location['is_default']:
                        print("\nUsing default location:")
                    else:
                        print("\nGPS Fix obtained:")
                    
                    print(f"Latitude:  {location['latitude']:.6f}°")
                    print(f"Longitude: {location['longitude']:.6f}°")
                    print(f"Altitude:  {location['altitude']:.1f}m")
                    print(f"Satellites: {location['satellites']}")
                    print(f"HDOP: {location['hdop']:.2f}")
                    
                    retry_count = 0
                    wait_time = 2  # Reset wait time on success
                else:
                    retry_count += 1
                    print(f"\nGPS read attempt {retry_count}/{max_retries} failed")
                    
                    if retry_count >= max_retries:
                        print("\nMultiple GPS read failures - checking module status")
                        if not self.send_command('AT', wait_time=1):
                            print("Module not responding, attempting to reinitialize...")
                            self.init_module()
                        retry_count = 0
                        wait_time = min(wait_time * 2, 30)  # Exponential backoff, max 30 seconds
                
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"Error in monitoring thread: {e}")
                time.sleep(5)

    def stop_monitoring(self):
        """Stop location monitoring."""
        self.running = False
        if hasattr(self, '_monitor_thread'):
            self._monitor_thread.join(timeout=2)
        print("Location monitoring stopped")

    def check_network_status(self):
        """Check current network registration status and signal quality."""
        if self.dev_mode:
            return True
            
        try:
            # Check SIM card status first
            sim_response = self.send_command('AT+CPIN?', wait_time=2)
            if not sim_response or 'READY' not in sim_response:
                print("\nSIM card not ready")
                print("Please check:")
                print("1. Is SIM card inserted properly?")
                print("2. Is SIM card activated?")
                print("3. Is PIN code disabled?")
                return False
                
            # Check signal quality
            signal_response = self.send_command('AT+CSQ', wait_time=1)
            signal_strength = 0
            if signal_response and '+CSQ:' in signal_response:
                try:
                    signal_strength = int(signal_response.split(': ')[1].split(',')[0])
                    print(f"\nSignal strength: {signal_strength}/31")
                    if signal_strength < self.MIN_SIGNAL_STRENGTH:
                        print("Warning: Weak signal - check GSM antenna")
                except:
                    print("Could not parse signal strength")
            
            # Enhanced network registration check
            reg_response = self.send_command('AT+CREG?', wait_time=2)
            if reg_response:
                if ',1' in reg_response:
                    self.network_registered = True
                    print("Successfully registered to home network")
                    return True
                elif ',5' in reg_response:
                    self.network_registered = True
                    print("Successfully registered to roaming network")
                    return True
                elif ',2' in reg_response:
                    print("Searching for network...")
                elif ',0' in reg_response:
                    print("Not registered, not searching")
                elif ',3' in reg_response:
                    print("Registration denied")
                elif ',4' in reg_response:
                    print("Unknown registration status")
                print(f"\nNetwork registration status: {reg_response}")
                return False
                
            print("Error checking network status")
            return False
            
        except Exception as e:
            print(f"Error checking network status: {e}")
            return False

    def init_network(self):
        """Initialize network connection with retry logic."""
        print("\nInitializing GSM network connection...")
        
        # Reset module first
        self.send_command('ATZ', wait_time=3)
        self.send_command('AT+CFUN=1,1', wait_time=10)  # Full functionality with reset
        
        # Wait for SIM card readiness
        for _ in range(5):
            sim_response = self.send_command('AT+CPIN?', wait_time=2)
            if sim_response and 'READY' in sim_response:
                print("SIM card ready")
                break
            print("Waiting for SIM card...")
            time.sleep(2)
        
        # Configure network settings
        self.send_command('AT+CREG=1')  # Enable network registration unsolicited result code
        self.send_command('AT+COPS=0')  # Set automatic network selection
        
        # Wait for network registration with retry logic
        retries = 0
        while retries < self.MAX_NETWORK_RETRIES:
            # Check signal strength first
            signal_response = self.send_command('AT+CSQ', wait_time=1)
            try:
                signal = int(signal_response.split(': ')[1].split(',')[0])
                print(f"\nSignal strength: {signal}/31")
                if signal < self.MIN_SIGNAL_STRENGTH:
                    print("Weak signal - waiting for better reception...")
                    time.sleep(self.NETWORK_RETRY_DELAY)
                    retries += 1
                    continue
            except:
                print("Could not parse signal strength")
            
            # Check registration status
            reg_response = self.send_command('AT+CREG?', wait_time=2)
            if reg_response:
                if ',1' in reg_response or ',5' in reg_response:
                    self.network_registered = True
                    print("\nSuccessfully registered to network!")
                    return True
                elif ',2' in reg_response:
                    print("Still searching for network...")
                else:
                    print(f"Network status: {reg_response}")
            
            retries += 1
            if retries < self.MAX_NETWORK_RETRIES:
                print(f"Retry {retries}/{self.MAX_NETWORK_RETRIES}: Waiting for network registration...")
                time.sleep(self.NETWORK_RETRY_DELAY)
        
        print("\nNetwork registration failed after maximum retries")
        print("Troubleshooting steps:")
        print("1. Check if SIM card is activated")
        print("2. Verify GSM antenna connection")
        print("3. Try moving to an area with better coverage")
        print("4. Contact network provider to verify subscription status")
        return False
