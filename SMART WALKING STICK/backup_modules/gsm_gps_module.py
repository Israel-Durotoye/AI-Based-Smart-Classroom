import serial
import time
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import threading
import glob
import sys
import os
import subprocess
import stat
import grp
import pwd

def validate_firebase_credentials(cred_path):
    """Validate Firebase credentials file"""
    try:
        if not os.path.exists(cred_path):
            print(f"Error: Firebase credentials file not found at {cred_path}")
            return False
            
        with open(cred_path, 'r') as f:
            cred_json = json.load(f)
            
        # Check for required fields in the credentials file
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in cred_json:
                print(f"Error: Missing required field '{field}' in Firebase credentials")
                return False
                
        # Verify it's a service account key
        if cred_json.get('type') != 'service_account':
            print("Error: Credentials file is not a service account key")
            return False
            
        return True
    except json.JSONDecodeError:
        print("Error: Firebase credentials file is not valid JSON")
        return False
    except Exception as e:
        print(f"Error validating Firebase credentials: {str(e)}")
        return False

def check_uart_config():
    """Check UART configuration on Raspberry Pi"""
    uart_status = {
        'config_txt': False,
        'devices': [],
        'permissions': False,
        'dtoverlay': False
    }
    
    print("\nChecking Raspberry Pi UART configuration...")
    
    # Check if UART is enabled in raspi-config
    try:
        uart_enabled = subprocess.check_output(['sudo', 'raspi-config', 'nonint', 'get_uart'])
        print(f"UART enabled in raspi-config: {uart_enabled.strip() == b'1'}")
    except:
        print("Could not check raspi-config UART status")
    
    # Check config.txt
    try:
        with open('/boot/config.txt', 'r') as f:
            config = f.read()
            uart_enabled = 'enable_uart=1' in config
            bluetooth_disabled = 'dtoverlay=disable-bt' in config
            print("\nBoot config status:")
            print(f"- enable_uart=1: {'Present' if uart_enabled else 'Missing'}")
            print(f"- dtoverlay=disable-bt: {'Present' if bluetooth_disabled else 'Missing'}")
            
            if not uart_enabled or not bluetooth_disabled:
                print("\nFix by adding these lines to /boot/config.txt:")
                if not uart_enabled:
                    print("enable_uart=1")
                if not bluetooth_disabled:
                    print("dtoverlay=disable-bt")
                print("Then reboot with: sudo reboot")
    except Exception as e:
        print(f"Error reading config.txt: {e}")
    
    # Check permissions
    try:
        import pwd
        username = pwd.getpwuid(os.getuid()).pw_name
        groups = subprocess.check_output(['groups', username]).decode()
        has_dialout = 'dialout' in groups
        print(f"\nPermissions check:")
        print(f"User: {username}")
        print(f"In dialout group: {has_dialout}")
        if not has_dialout:
            print("Fix with: sudo usermod -a -G dialout $USER")
    except Exception as e:
        print(f"Error checking permissions: {e}")
    
    # Check UART devices
    print("\nChecking UART devices:")
    uart_devices = ['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0']
    for device in uart_devices:
        try:
            if os.path.exists(device):
                st = os.stat(device)
                print(f"\n{device}:")
                print(f"- Exists: Yes")
                print(f"- Readable: {bool(st.st_mode & stat.S_IRUSR)}")
                print(f"- Writable: {bool(st.st_mode & stat.S_IWUSR)}")
                print(f"- Permissions: {oct(st.st_mode & 0o777)}")
                if os.path.islink(device):
                    real_path = os.path.realpath(device)
                    print(f"- Links to: {real_path}")
            else:
                print(f"\n{device}: Not found")
        except Exception as e:
            print(f"Error checking {device}: {e}")
    
    # Check if Bluetooth is disabled (which can interfere with UART)
    try:
        hciconfig = subprocess.check_output(['hciconfig'], stderr=subprocess.STDOUT).decode()
        print("\nBluetooth status:")
        if 'No such file or directory' in hciconfig:
            print("Bluetooth appears to be disabled (good)")
        else:
            print("Warning: Bluetooth appears to be enabled")
            print("Disable it by adding 'dtoverlay=disable-bt' to /boot/config.txt")
    except:
        print("Could not check Bluetooth status")
    
    return uart_status

def find_serial_port():
    """Find the correct serial port for the A9G module"""
    print("\nScanning for A9G module...")
    
    # Force set permissions for UART devices
    for device in ['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0']:
        try:
            if os.path.exists(device):
                subprocess.run(['sudo', 'chmod', '666', device], check=False)
        except:
            pass
    
    # Primary check for /dev/serial0
    if os.path.exists('/dev/serial0'):
        try:
            # Check if it's a symlink and where it points to
            if os.path.islink('/dev/serial0'):
                real_path = os.path.realpath('/dev/serial0')
                print(f"/dev/serial0 -> {real_path}")
            
            # Try to open and configure the port
            test_serial = serial.Serial(
                '/dev/serial0',
                baudrate=115200,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # Send AT command multiple times
            print("Testing communication with A9G module...")
            for _ in range(5):
                test_serial.write(b'AT\r\n')
                time.sleep(0.5)
                response = test_serial.read_all()
                if response:
                    print(f"Got response (hex): {response.hex()}")
                if b'OK' in response or b'>' in response:
                    print("Successfully connected to /dev/serial0")
                    test_serial.close()
                    return '/dev/serial0'
            
            test_serial.close()
            print("No valid response from A9G module on /dev/serial0")
            
        except Exception as e:
            print(f"Error with /dev/serial0: {e}")
            print("\nTroubleshooting steps:")
            print("1. Check physical connections:")
            print("   - A9G TX -> RPi RX (GPIO15, pin 10)")
            print("   - A9G RX -> RPi TX (GPIO14, pin 8)")
            print("   - A9G GND -> RPi GND")
            print("2. Verify UART is enabled:")
            print("   sudo raspi-config")
            print("   -> Interface Options -> Serial -> No to login shell, Yes to hardware")
            print("3. Check /boot/config.txt has:")
            print("   enable_uart=1")
            print("   dtoverlay=disable-bt")
            print("4. Verify power to A9G module:")
            print("   - LED should be stable")
            print("   - Measure voltage between VCC and GND (should be 3.3-4.2V)")
            return None
    
    print("Error: /dev/serial0 not found!")
    return None

class A9GModule:
    def __init__(self, baud_rate=115200):
        # Find available serial port
        port = find_serial_port()
        if port is None:
            print("Error: No suitable serial port found!")
            print("Please check:")
            print("1. Is the A9G module connected via USB?")
            print("2. Do you have permission to access serial ports?")
            print("   Try: sudo usermod -a -G dialout $USER")
            print("3. Is the USB-TTL adapter driver installed?")
            print("   Try: lsusb to see if the device is recognized")
            raise Exception("No suitable serial port found")

        try:
            self.serial = serial.Serial(port, baud_rate, timeout=1)
            print(f"Successfully connected to {port}")
            
            # Send initial test SMS
            self.target_number = "+2349069080731"  # Initialize number here
            test_message = "A9G Module Successfully Connected!\nInitializing GPS tracking..."
            if self.send_test_sms(test_message):
                print("Initial test SMS sent successfully")
            else:
                print("Failed to send test SMS - check GSM connection")
                
        except serial.SerialException as e:
            print(f"Error opening serial port {port}: {e}")
            raise

        self.gps_data = {'latitude': 0, 'longitude': 0, 'altitude': 0}
        self.last_update = 0
        self.running = True
        
        # Initialize Firebase with better error handling
        cred_path = "walking-stick-app-firebase-adminsdk-fbsvc-c9db4d30a3.json"
        try:
            # Validate credentials first
            if not validate_firebase_credentials(cred_path):
                raise Exception("Invalid Firebase credentials")
                
            # Print credential file contents for debugging
            with open(cred_path, 'r') as f:
                cred_content = json.load(f)
                print("\nFirebase project details:")
                print(f"Project ID: {cred_content.get('project_id', 'Not found')}")
                print(f"Client Email: {cred_content.get('client_email', 'Not found')}")
            
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://walking-stick-app-default-rtdb.firebaseio.com/'
            })
            self.ref = db.reference('gps_data')
            print("Firebase initialized successfully!")
            
        except Exception as e:
            print("\nFirebase initialization error!")
            print("Please check the following:")
            print("1. Is google-services.json in the correct location?")
            print("2. Did you download the correct service account key?")
            print("3. Has the service account been granted necessary permissions?")
            print(f"\nDetailed error: {str(e)}")
            raise

        # Phone numbers
        self.module_number = "+2349128892934"
        self.target_number = "+2349069080731"
        
        # Start GPS monitoring thread
        self.gps_thread = threading.Thread(target=self.monitor_gps)
        self.gps_thread.daemon = True
        self.gps_thread.start()

    def send_at_command(self, command, wait_time=1, check_response=True):
        """Send AT command with improved error handling and binary data support"""
        try:
            # Clear input buffer before sending command
            self.serial.reset_input_buffer()
            
            # Send command with CR+LF
            self.serial.write((command + '\r\n').encode())
            time.sleep(wait_time)
            
            # Read response in binary mode first
            raw_response = bytearray()
            start_time = time.time()
            
            while (time.time() - start_time) < wait_time:
                if self.serial.in_waiting:
                    new_data = self.serial.read(self.serial.in_waiting)
                    raw_response.extend(new_data)
                    if b'OK' in raw_response or b'ERROR' in raw_response:
                        break
                time.sleep(0.1)
            
            # Try to decode the response, handling potential encoding issues
            try:
                # First try UTF-8 decoding
                response = raw_response.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # If UTF-8 fails, try to decode as ASCII, ignoring non-ASCII bytes
                    response = raw_response.decode('ascii', errors='ignore')
                except:
                    # If all decoding fails, convert to hex for debugging
                    print(f"Warning: Could not decode response for command '{command}'")
                    print(f"Raw response (hex): {raw_response.hex()}")
                    return None if check_response else raw_response
            
            # Clean the response
            response = response.strip()
            
            if check_response:
                if 'ERROR' in response:
                    print(f"Command '{command}' failed with response: {response}")
                    return None
                if not response and command != 'AT':  # Empty response is OK for AT command
                    print(f"No response from module for command: {command}")
                    return None
            
            return response
            
        except serial.SerialException as e:
            print(f"Serial communication error for command '{command}': {e}")
            # Try to recover from serial errors
            try:
                self.serial.close()
                time.sleep(1)
                self.serial.open()
            except:
                pass
            return None
        except Exception as e:
            print(f"Error sending command '{command}': {e}")
            return None

    def init_module(self):
        """Initialize the A9G module with improved error handling"""
        print("\nInitializing A9G module...")
        
        # Configure serial port with explicit settings
        try:
            self.serial.close()  # Close first if already open
            self.serial.baudrate = 115200
            self.serial.bytesize = serial.EIGHTBITS
            self.serial.parity = serial.PARITY_NONE
            self.serial.stopbits = serial.STOPBITS_ONE
            self.serial.xonxoff = False     # Disable software flow control
            self.serial.rtscts = True       # Enable hardware flow control
            self.serial.dsrdtr = True       # Enable hardware flow control
            self.serial.timeout = 2         # Increase timeout for better reliability
            self.serial.write_timeout = 1   # Add write timeout
        
        # Force close and reopen the port to reset it
        try:
            self.serial.close()
            time.sleep(1)
            self.serial.open()
        except Exception as e:
            print(f"Error resetting serial port: {e}")
        
        # Flush any pending data
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        
        # Initial AT test with binary response handling
        print("\nTesting initial AT command...")
        success = False
        for _ in range(5):
            self.serial.write(b'AT\r\n')
            time.sleep(0.5)
            try:
                response = self.serial.read_all()
                if b'OK' in response:
                    success = True
                    print("Got OK response from module")
                    break
                else:
                    print(f"Unexpected response (hex): {response.hex()}")
            except Exception as e:
                print(f"Error reading response: {e}")
            time.sleep(0.5)
        
        if not success:
            print("\nInitial AT test failed. Trying different baud rates...")
            for baud in [9600, 38400, 115200]:
                print(f"\nTrying baud rate: {baud}")
                self.serial.baudrate = baud
                self.serial.reset_input_buffer()
                
                for _ in range(3):
                    try:
                        self.serial.write(b'AT\r\n')
                        time.sleep(0.5)
                        response = self.serial.read_all()
                        if b'OK' in response:
                            print(f"Success at {baud} baud")
                            success = True
                            break
                    except:
                        continue
                if success:
                    break
                time.sleep(0.5)
        
        if not success:
            print("\nFailed to establish communication. Hardware check required:")
            print("1. Verify voltage levels:")
            print("   - A9G VCC should be 3.3V-4.2V")
            print("   - Logic levels should match (3.3V)")
            print("2. Check connections:")
            print("   - A9G TX → RPi RX (GPIO15)")
            print("   - A9G RX → RPi TX (GPIO14)")
            print("   - Ensure good ground connection")
            print("3. Verify hardware:")
            print("   - Check power LED on A9G")
            print("   - Try power cycling the module")
            print("   - Measure voltage levels with multimeter")
            raise Exception("Module not responding to AT commands")
        
        # Continue with subsystem initialization
        print("\nConfiguring module subsystems...")
        
        # Get module info
        print("\nChecking module information...")
        self.send_at_command('ATI', wait_time=2)  # Get module info
        self.send_at_command('AT+CGMM', wait_time=1)  # Get model info
        
        # Configure SMS settings
        print("\nConfiguring SMS settings...")
        if not self.send_at_command('AT+CMGF=1', wait_time=1):  # Text mode
            print("Warning: Failed to set SMS text mode")
        if not self.send_at_command('AT+CSCS="GSM"', wait_time=1):  # Character set
            print("Warning: Failed to set character set")
        
        # Initialize GPS
        print("\nInitializing GPS subsystem...")
        gps_success = False
        for _ in range(3):
            if self.send_at_command('AT+GPS=1', wait_time=2):  # Turn on GPS
                if self.send_at_command('AT+GPSRD=1', wait_time=2):  # Enable GPS data reading
                    gps_success = True
                    print("GPS initialized successfully")
                    break
            time.sleep(2)
        
        if not gps_success:
            print("\nGPS initialization failed. Please check:")
            print("1. GPS antenna is connected")
            print("2. Clear view of the sky")
            print("3. Wait for first fix (can take several minutes)")
        
        # Check network registration
        print("\nChecking network registration...")
        network_registered = False
        for _ in range(5):
            response = self.send_at_command('AT+CREG?', wait_time=2)
            if response and (',1' in response or ',5' in response):
                network_registered = True
                print("GSM network registered successfully")
                break
            print("Waiting for network registration...")
            time.sleep(2)
        
        if not network_registered:
            print("\nNetwork registration failed. Please check:")
            print("1. SIM card is inserted properly")
            print("2. SIM card is activated")
            print("3. GSM antenna is connected")
            print("4. Signal strength in your area")
        
        # Check signal strength
        signal = self.send_at_command('AT+CSQ', wait_time=1)
        if signal:
            print(f"\nSignal strength: {signal}")
            if ',99' in signal or ',99,99' in signal:
                print("Warning: Poor signal strength or no signal")
        
        print("\nA9G module initialization completed")
        
        # Final validation - try to get GPS data
        print("\nValidating GPS functionality...")
        response = self.send_at_command('AT+LOCATION=2', wait_time=2)
        if response and ',' in response:
            print("GPS data reading successful")
            print(f"Initial position: {response}")
        else:
            print("Warning: Could not get GPS data yet - this is normal if GPS hasn't acquired a fix")

    def format_coordinate(self, value, direction):
        """Format coordinate to degrees with direction (N/S/E/W)"""
        if value is None or value == 0:
            return "No Fix"
            
        is_negative = value < 0
        abs_value = abs(value)
        
        if direction in ['N', 'S']:
            direction = 'S' if is_negative else 'N'
        else:  # E/W
            direction = 'W' if is_negative else 'E'
        
        return f"{abs_value:.4f}° {direction}"

    def send_sms(self, message):
        """Send SMS with current location"""
        try:
            # Set SMS text mode
            if not self.send_at_command('AT+CMGF=1'):
                print("Failed to set SMS text mode")
                return False
            
            # Set target number
            cmd = f'AT+CMGS="{self.target_number}"'
            if not self.send_at_command(cmd, wait_time=0.5):
                print("Failed to set SMS target number")
                return False
            
            # Send message content
            try:
                self.serial.write(message.encode() + b'\x1A')
                time.sleep(2)
                response = ''
                while self.serial.in_waiting:
                    response += self.serial.read().decode()
                
                if '+CMGS:' in response:
                    print("SMS sent successfully")
                    return True
                else:
                    print("SMS sending failed")
                    return False
            except Exception as e:
                print(f"Error sending SMS content: {e}")
                return False
        except Exception as e:
            print(f"SMS sending error: {e}")
            return False

    def update_firebase(self):
        """Update Firebase with current GPS data"""
        try:
            data = {
                'latitude': self.gps_data['latitude'],
                'longitude': self.gps_data['longitude'],
                'altitude': self.gps_data['altitude'],
                'timestamp': time.time()
            }
            self.ref.set(data)
            return True
        except Exception as e:
            print(f"Firebase update error: {str(e)}")
            return False

    def format_gps_message(self):
        """Format GPS data into a detailed message"""
        if not self.gps_data.get('fix', False):
            return "GPS: No Fix Available"
            
        message = "Location Update:\n"
        message += f"Position: {self.format_coordinate(self.gps_data['latitude'], 'N')}, "
        message += f"{self.format_coordinate(self.gps_data['longitude'], 'E')}\n"
        message += f"Altitude: {self.gps_data['altitude']:.1f}m\n"
        
        if self.gps_data.get('speed', 0) > 0:
            message += f"Speed: {self.gps_data['speed']:.1f} km/h\n"
        if self.gps_data.get('course', 0) > 0:
            message += f"Heading: {self.gps_data['course']:.1f}°\n"
        if self.gps_data.get('satellites', 0) > 0:
            message += f"Satellites: {self.gps_data['satellites']}\n"
        
        return message

    def check_gps_status(self):
        """Check GPS subsystem status and provide diagnostic info"""
        try:
            # Check if GPS is powered on
            gps_power = self.send_at_command('AT+GPS?', wait_time=1)
            print(f"\nGPS Power Status: {gps_power}")
            
            if not gps_power or '+GPS: 0' in gps_power:
                print("GPS is powered off, attempting to power on...")
                self.send_at_command('AT+GPS=1', wait_time=2)
                time.sleep(2)  # Wait for GPS to initialize
            
            # Check GPS read mode
            gps_read = self.send_at_command('AT+GPSRD?', wait_time=1)
            print(f"GPS Read Mode: {gps_read}")
            
            # Get detailed GPS info
            gnss_info = self.send_at_command('AT+CGNSSINFO', wait_time=2)
            print(f"GNSS Info: {gnss_info}")
            
            # Force a GPS cold start if no fix
            if ('0,0.000000,0.000000' in gnss_info) or ('ERROR' in str(gnss_info)):
                print("No GPS fix, attempting cold start...")
                self.send_at_command('AT+GPSCLR', wait_time=1)  # Clear GPS data
                self.send_at_command('AT+GPS=0', wait_time=1)   # Power off GPS
                time.sleep(2)
                self.send_at_command('AT+GPS=1', wait_time=1)   # Power on GPS
                self.send_at_command('AT+GPSRD=1', wait_time=1) # Enable GPS data
                print("GPS reset complete, waiting for fix...")
                
            return True
        except Exception as e:
            print(f"Error checking GPS status: {e}")
            return False

    def init_gnss(self):
        """Initialize and power on GNSS subsystem with proper error handling."""
        print("\nInitializing GNSS subsystem...")
        
        # First check current GNSS power status
        response = self.send_at_command('AT+CGNSPWR?')
        if not response:
            print("Error: Failed to check GNSS power status")
            return False
        
        # Power on GNSS if needed
        if '+CGNSPWR: 0' in response:
            print("GNSS is powered off. Powering on...")
            if not self.send_at_command('AT+CGNSPWR=1', wait_time=2):
                print("Error: Failed to power on GNSS")
                return False
            time.sleep(2)  # Wait for GNSS to initialize
            
            # Verify power status again
            response = self.send_at_command('AT+CGNSPWR?')
            if not response or '+CGNSPWR: 1' not in response:
                print("Error: GNSS failed to power on")
                return False
        
        print("GNSS powered on successfully")
        
        # Enable NMEA debug output if needed
        if self.debug_mode:
            print("Enabling NMEA debug output...")
            if self.send_at_command('AT+CGNSTST=1', wait_time=1):
                print("NMEA debug output enabled")
            else:
                print("Warning: Failed to enable NMEA debug output")
        
        # Configure GNSS parameters
        print("Configuring GNSS parameters...")
        
        # Set automatic GPS operation (1=auto)
        self.send_at_command('AT+CGNSMOD=1')
        
        # Check GNSS information
        gnss_info = self.get_gnss_info()
        if gnss_info:
            print("\nGNSS Status:")
            print(f"Run status: {gnss_info['run_status']}")
            print(f"Fix status: {gnss_info['fix_status']}")
            print(f"Satellites in view: {gnss_info['satellites_view']}")
            
        return True
        
    def get_gnss_info(self):
        """Get detailed GNSS information from the module.
        
        Returns:
            dict: GNSS status information or None on error
        """
        try:
            response = self.send_at_command('AT+CGNSINF', wait_time=2)
            if not response or 'ERROR' in response:
                print("Error getting GNSS information")
                return None
                
            # Response format: +CGNSINF: <GNSS run status>,<Fix status>,<UTC date & time>,
            # <Latitude>,<Longitude>,<MSL Altitude>,<Speed Over Ground>,<Course Over Ground>,
            # <Fix Mode>,<Reserved1>,<HDOP>,<PDOP>,<VDOP>,<Reserved2>,<Satellites in View>,...
            parts = response.split('+CGNSINF: ')[1].split(',')
            if len(parts) < 15:
                print("Incomplete GNSS information")
                return None
                
            return {
                'run_status': int(parts[0]),
                'fix_status': int(parts[1]),
                'utc_time': parts[2],
                'latitude': float(parts[3]) if parts[3] else 0.0,
                'longitude': float(parts[4]) if parts[4] else 0.0,
                'altitude': float(parts[5]) if parts[5] else 0.0,
                'speed': float(parts[6]) if parts[6] else 0.0,
                'course': float(parts[7]) if parts[7] else 0.0,
                'fix_mode': int(parts[8]) if parts[8] else 0,
                'hdop': float(parts[10]) if parts[10] else 0.0,
                'pdop': float(parts[11]) if parts[11] else 0.0,
                'vdop': float(parts[12]) if parts[12] else 0.0,
                'satellites_view': int(parts[14]) if parts[14] else 0
            }
            
        except (IndexError, ValueError, TypeError) as e:
            print(f"Error parsing GNSS information: {e}")
            print(f"Raw response: {response}")
            return None
            
        except Exception as e:
            print(f"Unexpected error getting GNSS info: {e}")
            return None

    def get_gps_data(self, max_retries=3, retry_delay=5):
        """Get GPS location data with retry logic.
        
        Args:
            max_retries (int): Maximum number of attempts to get a GPS fix
            retry_delay (int): Delay in seconds between retries
            
        Returns:
            tuple: (latitude, longitude) if successful, None otherwise
        """
        print("\nAttempting to get GPS location...")
        
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"\nRetry attempt {attempt + 1} of {max_retries}")
                time.sleep(retry_delay)
            
            # Get GNSS information
            gnss_info = self.get_gnss_info()
            if not gnss_info:
                print("Failed to get GNSS information")
                continue
                
            # Check if GNSS is running
            if gnss_info['run_status'] != 1:
                print("GNSS is not running. Attempting to initialize...")
                if not self.init_gnss():
                    continue
                time.sleep(2)  # Wait for initialization
                gnss_info = self.get_gnss_info()
                if not gnss_info:
                    continue
            
            # Check fix status
            if gnss_info['fix_status'] != 1:
                print(f"No GPS fix. Satellites in view: {gnss_info['satellites_view']}")
                print("Waiting for fix...")
                continue
            
            # Validate coordinates
            lat = gnss_info['latitude']
            lon = gnss_info['longitude']
            
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat != 0 or lon != 0):
                print(f"\nGPS Fix obtained!")
                print(f"Latitude: {lat:.6f}")
                print(f"Longitude: {lon:.6f}")
                print(f"Altitude: {gnss_info['altitude']:.1f}m")
                print(f"Satellites: {gnss_info['satellites_view']}")
                print(f"HDOP: {gnss_info['hdop']}")
                return lat, lon
            else:
                print("Invalid coordinates received")
                
        print("\nFailed to get valid GPS location after maximum retries")
        
        # Check if it's time to send default location
        current_time = time.time()
        if current_time - self.last_default_send >= self.default_send_interval:
            print("\nSending default location as fallback...")
            self.last_default_send = current_time
            return self.default_latitude, self.default_longitude
            
        return None
        
    def send_location_sms(self, phone_number, max_retries=2):
        """Send current location via SMS with retry logic.
        
        Args:
            phone_number (str): The phone number to send the SMS to
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            bool: True if SMS was sent successfully, False otherwise
        """
        location = self.get_gps_data(max_retries=max_retries)
        if not location:
            error_msg = "Unable to get GPS location for SMS"
            print(error_msg)
            # Send error notification
            self.send_sms(phone_number, f"Error: {error_msg}")
            return False
            
        lat, lon = location
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        message = f"Current Location:\nLatitude: {lat:.6f}\nLongitude: {lon:.6f}\nMaps: {maps_link}"
        
        return self.send_sms(phone_number, message)

    def monitor_gps(self):
        """Continuous GPS monitoring with improved error handling"""
        retry_count = 0
        max_retries = 5
        wait_time = 2  # Initial wait time between retries
        
        while self.running:
            try:
                location = self.get_gps_data()
                if location:
                    current_time = time.time()
                    lat, lon = location
                    retry_count = 0
                    wait_time = 2  # Reset wait time on success
                    
                    # Update GPS data structure
                    self.gps_data['latitude'] = lat
                    self.gps_data['longitude'] = lon
                    
                    # Indicate if using default location
                    if lat == self.default_latitude and lon == self.default_longitude:
                        print("\nUsing default location due to GPS signal issues")
                        # Set other GPS data fields for default location
                        self.gps_data['altitude'] = 0.0
                        self.gps_data['speed'] = 0.0
                        self.gps_data['course'] = 0.0
                        self.gps_data['fix'] = True  # Mark as having a "fix" so messages will be sent
                    
                    # Format message
                    message = self.format_gps_message()
                    print(f"\n{message}")
                    
                    # Update Firebase and send SMS every 30 seconds
                    if current_time - self.last_update >= 30:
                        firebase_success = self.update_firebase()
                        sms_success = self.send_sms(message)
                        
                        if firebase_success and sms_success:
                            self.last_update = current_time
                        else:
                            print("Failed to update Firebase or send SMS")
                
                else:
                    retry_count += 1
                    print(f"\nGPS read attempt {retry_count}/{max_retries} failed")
                    
                    if retry_count >= max_retries:
                        print("\nMultiple GPS read failures, performing diagnostics...")
                        if not self.send_at_command('AT', wait_time=1):
                            print("Module not responding, attempting to reinitialize...")
                            self.init_module()
                        else:
                            self.check_gps_status()
                        retry_count = 0
                        wait_time = min(wait_time * 2, 30)  # Exponential backoff, max 30 seconds
                    
                    time.sleep(wait_time)
                    continue
                    
            except Exception as e:
                print(f"Error in GPS monitoring: {e}")
                time.sleep(5)
                continue
            
            time.sleep(1)  # Normal wait between readings

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up A9G module resources...")
        self.running = False
        if hasattr(self, 'serial') and self.serial.is_open:
            try:
                self.send_at_command('AT+GPS=0')  # Turn off GPS
                self.serial.close()
                print("A9G module cleaned up successfully")
            except Exception as e:
                print(f"Error during cleanup: {e}")

    def read_gps(self):
        """Read GPS data from module"""
        try:
            # Check if GPS is enabled
            self.send_command('AT+CGPS?')
            if '+CGPS: 1' not in self.read_response():
                print("GPS is not enabled")
                return None

            # Request NMEA GNGGA sentences
            self.send_command('AT+CGPSOUT=2')
            response = self.read_response(timeout=2)
            
            if not response:
                print("No GPS data available")
                return None

            # Look for GNGGA sentence
            gngga_lines = [line.strip() for line in response.split('\n') if line.startswith('$GNGGA')]
            if not gngga_lines:
                print("No valid GNGGA sentence found")
                return None
                
            # Parse GNGGA sentence
            parts = gngga_lines[0].split(',')
            gps_data = parse_gngga(parts)
            
            # Disable NMEA output
            self.send_command('AT+CGPSOUT=0')
            return gps_data
                
        except Exception as e:
            print(f"Error reading GPS: {e}")
            return None

    def send_test_sms(self, message):
        """Send a test SMS message with basic error handling.
        
        Args:
            message: The message to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize GSM
            init_commands = [
                ('AT', 1),                    # Basic AT test
                ('AT+CMGF=1', 1),            # Set SMS text mode
                ('AT+CSCS="GSM"', 1),        # Set GSM character set
                ('AT+CMGS="' + self.target_number + '"', 2)  # Set recipient
            ]
            
            # Execute initialization commands
            for cmd, wait_time in init_commands:
                response = self.send_at_command(cmd, wait_time=wait_time)
                if not response or 'ERROR' in str(response):
                    print(f"SMS init failed at command: {cmd}")
                    print(f"Response: {response}")
                    return False
                time.sleep(0.5)  # Small delay between commands
            
            # Send message content with message terminator
            self.serial.write(message.encode() + b'\x1A')
            time.sleep(3)  # Wait for send completion
            
            # Check for success response
            response = self.serial.read_all().decode('utf-8', errors='ignore')
            if '+CMGS:' in response:
                return True
                
            print(f"Unexpected response: {response}")
            return False
            
        except Exception as e:
            print(f"Error sending test SMS: {e}")
            return False

    def test_gps_sms(self, phone_number):
        """Test GPS and SMS functionality.
        
        Args:
            phone_number (str): Phone number to send test SMS to
            
        Returns:
            bool: True if all tests pass, False otherwise
        """
        print("\nTesting GPS and SMS functionality...")
        
        # Step 1: Initialize GNSS
        print("\n1. Testing GNSS initialization...")
        if not self.init_gnss():
            print("❌ GNSS initialization failed")
            return False
        print("✓ GNSS initialized successfully")
        
        # Step 2: Wait for initial GNSS data
        print("\n2. Waiting for initial GNSS data...")
        time.sleep(5)  # Give some time for satellites acquisition
        gnss_info = self.get_gnss_info()
        if not gnss_info:
            print("❌ Failed to get GNSS information")
            return False
        print("✓ GNSS information received")
        print(f"Satellites in view: {gnss_info['satellites_view']}")
        
        # Step 3: Test GPS fix
        print("\n3. Testing GPS location acquisition...")
        location = self.get_gps_data(max_retries=2)
        if not location:
            print("❌ Failed to get GPS location")
            return False
        print("✓ GPS location acquired successfully")
        
        # Step 4: Test SMS
        print("\n4. Testing SMS functionality...")
        print(f"Sending test SMS to {phone_number}")
        test_message = "Smart Walking Stick GPS Test: System initialized successfully!"
        if not self.send_sms(phone_number, test_message):
            print("❌ Failed to send test SMS")
            return False
        print("✓ Test SMS sent successfully")
        
        # Step 5: Test location SMS
        print("\n5. Testing location SMS...")
        if not self.send_location_sms(phone_number):
            print("❌ Failed to send location SMS")
            return False
        print("✓ Location SMS sent successfully")
        
        print("\nAll tests completed successfully! ✓")
        return True

def parse_gngga(gngga_parts):
    """Parse GNGGA (Global Navigation System Fix Data) sentence.
    
    Args:
        gngga_parts (list): Parts of the GNGGA sentence
        
    Returns:
        dict: Parsed GPS data or None on error
    """
    try:
        if len(gngga_parts) < 15:
            return None
            
        return {
            'utc_time': gngga_parts[1],
            'latitude': float(gngga_parts[2]) if gngga_parts[2] else 0.0,
            'lat_dir': gngga_parts[3],
            'longitude': float(gngga_parts[4]) if gngga_parts[4] else 0.0,
            'lon_dir': gngga_parts[5],
            'quality': int(gngga_parts[6]) if gngga_parts[6] else 0,
            'satellites': int(gngga_parts[7]) if gngga_parts[7] else 0,
            'hdop': float(gngga_parts[8]) if gngga_parts[8] else 0.0,
            'altitude': float(gngga_parts[9]) if gngga_parts[9] else 0.0,
            'altitude_unit': gngga_parts[10]
        }
    except (ValueError, IndexError) as e:
        print(f"Error parsing GNGGA data: {e}")
        return None

class GSMGPS:
    """A class to handle GPS and GSM functionality using A9G module."""
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, debug_mode=False):
        """Initialize the GSM/GPS module."""
        self.port = port
        self.baudrate = baudrate
        self.debug_mode = debug_mode
        self.serial = None
        self.connected = False
        
        # Default location coordinates (9.6560° N, 6.5287° E)
        self.default_latitude = 9.6560
        self.default_longitude = 6.5287
        self.last_default_send = 0  # Timestamp for last default location sent
        self.default_send_interval = 60  # Send default location every 60 seconds

        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            self.connected = True
            print(f"Connected to {self.port} at {self.baudrate} baud")
            
            # Initialize module
            if self.test_at():
                print("Module responded to AT command")
                self.send_at_command('ATE0')  # Disable echo
            else:
                print("Warning: Module not responding to AT commands")
                
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            self.connected = False
            
    def __del__(self):
        """Clean up resources."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            
    def test_at(self):
        """Test if module responds to AT commands.
        
        Returns:
            bool: True if module responds, False otherwise
        """
        return self.send_at_command('AT', wait_time=1) is not None
        
    def send_at_command(self, command, wait_time=1):
        """Send AT command to module and get response.
        
        Args:
            command (str): AT command to send
            wait_time (float): Time to wait for response in seconds
            
        Returns:
            str: Response from module or None on error
        """
        if not self.connected or not self.serial:
            print("Error: Not connected to module")
            return None
            
        try:
            # Clear input buffer
            self.serial.reset_input_buffer()
            
            # Send command
            cmd = f"{command}\r\n"
            self.serial.write(cmd.encode())
            
            if self.debug_mode:
                print(f"Sent: {command}")
            
            # Wait for response
            time.sleep(wait_time)
            
            # Read response
            response = ''
            while self.serial.in_waiting:
                response += self.serial.read().decode()
                
            if self.debug_mode:
                print(f"Received: {response}")
                
            return response
            
        except Exception as e:
            print(f"Error sending AT command: {e}")
            return None
            
    def send_sms(self, phone_number, message):
        """Send SMS message.
        
        Args:
            phone_number (str): Recipient phone number
            message (str): Message text
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Set SMS text mode
            if not self.send_at_command('AT+CMGF=1'):
                print("Error: Failed to set SMS text mode")
                return False
                
            # Set recipient number
            if not self.send_at_command(f'AT+CMGS="{phone_number}"', wait_time=2):
                print("Error: Failed to set recipient number")
                return False
                
            # Send message content
            response = self.send_at_command(f"{message}\x1A", wait_time=10)
            if not response or 'ERROR' in response:
                print("Error sending SMS")
                return False
                
            print("SMS sent successfully")
            return True
            
        except Exception as e:
            print(f"Error in send_sms: {e}")
            return False