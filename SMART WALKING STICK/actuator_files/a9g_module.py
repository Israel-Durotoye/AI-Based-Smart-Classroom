import serial
import time
import json
import firebase_admin
from firebase_admin import credentials, db
import threading

class A9GModule:
    def __init__(self, port='/dev/serial0', baud_rate=115200):
        """Initialize A9G GPS/GSM module"""
        try:
            self.serial = serial.Serial(port, baud_rate, timeout=1)
            print(f"Connected to {port}")
        except serial.SerialException as e:
            print(f"Error opening port {port}: {e}")
            raise

        # Initialize basic state
        self.gps_data = {'latitude': 0, 'longitude': 0, 'altitude': 0, 'fix': False}
        self.running = True
        self.gps_enabled = False
        self.agps_enabled = False
        self.gps_power_mode = 'normal'  # 'normal' or 'low_power'
        self.gps_update_interval = 1  # Default NMEA update interval in seconds
        
        # Initialize Firebase
        self._init_firebase()
        
        # Start GPS monitoring
        self.gps_thread = threading.Thread(target=self._monitor_gps)
        self.gps_thread.daemon = True
        self.gps_thread.start()

    def _init_firebase(self):
        """Initialize Firebase connection"""
        try:
            cred = credentials.Certificate("walking-stick-app-firebase-adminsdk-fbsvc-3c09a7dcb7.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://walking-stick-app-default-rtdb.firebaseio.com/'
            })
            self.db_ref = db.reference('gps_data')
            print("Firebase initialized")
        except Exception as e:
            print(f"Firebase initialization error: {e}")
            raise

    def send_command(self, command, wait_time=1):
        """Send AT command and get response"""
        try:
            self.serial.write(f"{command}\r\n".encode())
            time.sleep(wait_time)
            response = self.serial.read_all().decode('utf-8', errors='ignore').strip()
            return response
        except Exception as e:
            print(f"Error sending command {command}: {e}")
            return None

    def enable_gps(self, enable=True):
        """Enable or disable GPS."""
        try:
            if enable and self.agps_enabled:
                print("Disabling AGPS before enabling standard GPS")
                self.enable_agps(False)
            
            command = 'AT+GPS=1' if enable else 'AT+GPS=0'
            response = self.send_command(command)
            
            if 'OK' in response:
                self.gps_enabled = enable
                print(f"GPS {'enabled' if enable else 'disabled'} successfully")
                return True
            else:
                print(f"Failed to {'enable' if enable else 'disable'} GPS")
                return False
        except Exception as e:
            print(f"Error {'enabling' if enable else 'disabling'} GPS: {e}")
            return False

    def enable_agps(self, enable=True):
        """Enable or disable Assisted GPS (AGPS)."""
        try:
            if enable and self.gps_enabled:
                print("Disabling standard GPS before enabling AGPS")
                self.enable_gps(False)
            
            command = 'AT+AGPS=1' if enable else 'AT+AGPS=0'
            response = self.send_command(command)
            
            if 'OK' in response:
                self.agps_enabled = enable
                if enable:
                    print("AGPS enabled successfully. Note: Network connection required for AGPS.")
                else:
                    print("AGPS disabled successfully")
                return True
            else:
                print(f"Failed to {'enable' if enable else 'disable'} AGPS")
                return False
        except Exception as e:
            print(f"Error {'enabling' if enable else 'disabling'} AGPS: {e}")
            return False

    def set_gps_power_mode(self, low_power=True):
        """Set GPS power mode (normal or low power)."""
        try:
            command = 'AT+GPSLP=2' if low_power else 'AT+GPSLP=1'
            response = self.send_command(command)
            
            if 'OK' in response:
                self.gps_power_mode = 'low_power' if low_power else 'normal'
                print(f"GPS power mode set to {'low power' if low_power else 'normal'}")
                return True
            else:
                print("Failed to set GPS power mode")
                return False
        except Exception as e:
            print(f"Error setting GPS power mode: {e}")
            return False

    def set_gps_update_interval(self, interval=1):
        """Set GPS NMEA update interval in seconds."""
        try:
            command = f'AT+GPSRD={interval}'
            response = self.send_command(command)
            
            if 'OK' in response:
                self.gps_update_interval = interval
                print(f"GPS update interval set to {interval} seconds")
                return True
            else:
                print("Failed to set GPS update interval")
                return False
        except Exception as e:
            print(f"Error setting GPS update interval: {e}")
            return False

    def get_location_source(self, source_type=2):
        """Get location from specified source (1=base station, 2=GPS)."""
        try:
            command = f'AT+LOCATION={source_type}'
            response = self.send_command(command, wait_time=3)
            
            if source_type == 1:
                print("Getting location from base station")
            else:
                print("Getting location from GPS")
                
            return response
        except Exception as e:
            print(f"Error getting location from source {source_type}: {e}")
            return None

    def check_gps_status(self):
        """Check GPS status."""
        try:
            gps_response = self.send_command('AT+GPS?')
            agps_response = self.send_command('AT+AGPS?')
            
            status = {
                'gps_enabled': '+GPS: 1' in gps_response,
                'agps_enabled': '+AGPS: 1' in agps_response,
                'power_mode': self.gps_power_mode,
                'update_interval': self.gps_update_interval
            }
            
            print("\nGPS Status:")
            print(f"GPS Enabled: {status['gps_enabled']}")
            print(f"AGPS Enabled: {status['agps_enabled']}")
            print(f"Power Mode: {status['power_mode']}")
            print(f"Update Interval: {status['update_interval']} seconds")
            
            return status
        except Exception as e:
            print(f"Error checking GPS status: {e}")
            return None

    def _parse_gps(self, data):
        """Parse GPS data from NMEA format"""
        try:
            parts = data.split(',')
            if len(parts) < 10:
                return None

            # Convert NMEA coordinates (DDMM.MMMM) to decimal degrees
            lat = float(parts[2][:2]) + float(parts[2][2:]) / 60
            lon = float(parts[4][:3]) + float(parts[4][3:]) / 60
            
            # Apply direction
            if parts[3] == 'S': lat = -lat
            if parts[5] == 'W': lon = -lon
            
            return {
                'fix': True,
                'latitude': lat,
                'longitude': lon,
                'altitude': float(parts[9]) if parts[9] else 0,
                'satellites': int(parts[7]) if parts[7] else 0,
                'timestamp': time.time()
            }
        except Exception:
            return None

    def read_gps(self):
        """Read current GPS data"""
        response = self.send_command('AT+CGPSOUT=2', wait_time=2)
        if not response:
            return None
            
        # Look for GNGGA sentence
        for line in response.split('\n'):
            if line.startswith('$GNGGA'):
                gps_data = self._parse_gps(line)
                if gps_data:
                    self.gps_data = gps_data
                    return gps_data
        return None

    def _monitor_gps(self):
        """Continuously monitor GPS data"""
        last_update = 0
        update_interval = 30  # seconds
        
        while self.running:
            try:
                gps_data = self.read_gps()
                if gps_data:
                    current_time = time.time()
                    if current_time - last_update >= update_interval:
                        self.db_ref.set(gps_data)
                        last_update = current_time
            except Exception as e:
                print(f"GPS monitoring error: {e}")
            time.sleep(1)

    def get_location(self):
        """Get current location data"""
        return self.gps_data

    def send_sms(self, number, message):
        """Send SMS with the provided message"""
        try:
            self.send_command('AT+CMGF=1')  # Text mode
            self.send_command(f'AT+CMGS="{number}"', wait_time=1)
            self.serial.write(message.encode() + b'\x1A')
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if hasattr(self, 'serial'):
            # Disable AGPS if enabled
            if self.agps_enabled:
                self.enable_agps(False)
            
            # Disable GPS if enabled
            if self.gps_enabled:
                self.enable_gps(False)
            
            # Close serial connection
            self.serial.close()

    def init_module(self):
        """Initialize the module's GPS and GSM functionality with optimal settings."""
        try:
            # Test communication
            if 'OK' not in self.send_command('AT'):
                raise Exception("Module not responding")

            # Initialize network first (recommended for AGPS)
            if self.check_network_status():
                print("Network registered successfully")
                
                # Try AGPS first for faster initial fix
                if self.enable_agps(True):
                    print("AGPS enabled for faster initial fix")
                else:
                    print("AGPS failed, falling back to standard GPS")
                    if not self.enable_gps(True):
                        raise Exception("Failed to enable GPS")
            else:
                print("No network available, using standard GPS")
                if not self.enable_gps(True):
                    raise Exception("Failed to enable GPS")

            # Set update interval (1 second for initial fix)
            self.set_gps_update_interval(1)
            
            # Wait for initial fix
            print("Waiting for initial GPS fix...")
            max_wait = 60  # Maximum wait time in seconds
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait:
                location = self.get_location()
                if location['valid']:
                    print(f"Initial fix obtained: {location['latitude']:.6f}, {location['longitude']:.6f}")
                    
                    # Switch to low power mode and reduce update frequency
                    self.set_gps_power_mode(True)
                    self.set_gps_update_interval(10)
                    return True
                time.sleep(1)
                
            print("Warning: Could not get initial GPS fix")
            return False
            
        except Exception as e:
            print(f"Error initializing module: {e}")
            return False

def main():
    """Example usage"""
    try:
        module = A9GModule()
        module.init_module()
        
        # Main loop
        try:
            while True:
                location = module.get_location()
                if location['fix']:
                    print(f"Location: {location['latitude']:.6f}, {location['longitude']:.6f}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            module.cleanup()
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
