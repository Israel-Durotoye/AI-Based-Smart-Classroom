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
        
        # Initialize Firebase
        self._init_firebase()
        
        # Start GPS monitoring
        self.gps_thread = threading.Thread(target=self._monitor_gps)
        self.gps_thread.daemon = True
        self.gps_thread.start()

    def _init_firebase(self):
        """Initialize Firebase connection"""
        try:
            cred = credentials.Certificate("walking-stick-app-firebase-adminsdk-fbsvc-c9db4d30a3.json")
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

    def init_module(self):
        """Initialize the module's GPS and GSM functionality"""
        # Test communication
        if 'OK' not in self.send_command('AT'):
            raise Exception("Module not responding")
            
        # Initialize GPS
        self.send_command('AT+GPS=1')  # Turn on GPS
        self.send_command('AT+GPSRD=1')  # Enable GPS data
        
        print("Module initialized successfully")

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
            self.send_command('AT+GPS=0')  # Turn off GPS
            self.serial.close()

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
