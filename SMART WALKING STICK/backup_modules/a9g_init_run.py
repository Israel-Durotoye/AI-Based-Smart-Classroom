#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import json
import firebase_admin
from firebase_admin import credentials, db
import threading

class A9GInitializer:
    def __init__(self, port='/dev/serial0', baud_rate=115200):
        self.port = port
        self.baud_rate = baud_rate
        self.serial = None
        self.default_location = (9.6560, 6.5287)  # Default location coordinates
        self.running = True
        self.last_location_update = 0
        self.update_interval = 60  # Send location update every 60 seconds
        
        # Initialize Firebase
        try:
            cred = credentials.Certificate("walking-stick-app-firebase-adminsdk-fbsvc-3c09a7dcb7.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://walking-stick-app-default-rtdb.firebaseio.com/'
            })
            self.db_ref = db.reference('gps_data')
            print("Firebase initialized successfully")
        except Exception as e:
            print(f"Firebase initialization error: {e}")
    
    def init_serial(self):
        """Initialize serial connection with proper error handling"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2,
                xonxoff=False,
                rtscts=True,
                dsrdtr=True
            )
            
            if not self.serial.is_open:
                self.serial.open()
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            print(f"Serial port {self.port} opened successfully")
            return True
            
        except Exception as e:
            print(f"Serial initialization error: {e}")
            return False
    
    def send_at_command(self, command, wait_time=1):
        """Send AT command with improved error handling"""
        if not self.serial:
            return None
            
        try:
            # Clear any pending data
            self.serial.reset_input_buffer()
            
            # Send command
            cmd = f"{command}\r\n"
            self.serial.write(cmd.encode())
            time.sleep(wait_time)
            
            # Read response with timeout
            response = bytearray()
            start_time = time.time()
            
            while (time.time() - start_time) < wait_time:
                if self.serial.in_waiting:
                    new_data = self.serial.read(self.serial.in_waiting)
                    response.extend(new_data)
                    if b'OK' in response or b'ERROR' in response:
                        break
                time.sleep(0.1)
            
            return response.decode('utf-8', errors='ignore').strip()
            
        except Exception as e:
            print(f"AT command error ({command}): {e}")
            return None
    
    def init_module(self):
        """Initialize A9G module with all necessary configurations"""
        print("\nInitializing A9G module...")
        
        # Basic AT test
        response = self.send_at_command("AT")
        if not response or "OK" not in response:
            print("Failed basic AT test")
            return False
        
        # Configure SMS text mode
        if not self.send_at_command("AT+CMGF=1"):
            print("Failed to set SMS text mode")
            return False
        
        # Configure GPS
        print("\nInitializing GPS...")
        if not self.send_at_command("AT+CGPS=1"):
            print("Failed to enable GPS")
            return False
        
        # Check network registration
        response = self.send_at_command("AT+CREG?")
        if response and (",1" in response or ",5" in response):
            print("Network registered")
        else:
            print("Warning: Not registered to network")
        
        return True
    
    def monitor_location(self):
        """Monitor and update location data"""
        while self.running:
            try:
                current_time = time.time()
                
                # Send location update every 60 seconds
                if current_time - self.last_location_update >= self.update_interval:
                    # Try to get GPS location
                    response = self.send_at_command("AT+CGPSINFO")
                    
                    if response and "+CGPSINFO:" in response:
                        print("\nGPS data received:", response)
                        # Real GPS data available - parse and send
                        try:
                            parts = response.split(":")[1].strip().split(",")
                            if len(parts) >= 4 and parts[0]:
                                lat = float(parts[0])
                                lon = float(parts[2])
                                self.update_firebase_location(lat, lon, False)
                                print(f"Updated location: {lat}, {lon}")
                            else:
                                self.use_default_location()
                        except:
                            self.use_default_location()
                    else:
                        self.use_default_location()
                    
                    self.last_location_update = current_time
                
                time.sleep(5)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(5)
    
    def use_default_location(self):
        """Send default location when GPS is not available"""
        print("\nUsing default location")
        self.update_firebase_location(self.default_location[0], self.default_location[1], True)
    
    def update_firebase_location(self, lat, lon, is_default=False):
        """Update location in Firebase"""
        try:
            data = {
                'latitude': lat,
                'longitude': lon,
                'timestamp': time.time(),
                'is_default': is_default
            }
            self.db_ref.set(data)
            print("Firebase location updated successfully")
        except Exception as e:
            print(f"Firebase update error: {e}")
    
    def start(self):
        """Start the A9G module monitoring"""
        if not self.init_serial():
            return False
        
        if not self.init_module():
            return False
        
        # Start location monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_location)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print("\nA9G module initialized and monitoring started")
        return True
    
    def stop(self):
        """Stop monitoring and cleanup"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        if self.serial:
            self.serial.close()

def main():
    """Main function to run the A9G initializer"""
    try:
        # Try different serial ports
        ports = ['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0']
        a9g = None
        
        for port in ports:
            print(f"\nTrying port: {port}")
            a9g = A9GInitializer(port=port)
            if a9g.start():
                print(f"Successfully initialized on {port}")
                break
            else:
                print(f"Failed to initialize on {port}")
        
        if a9g and a9g.running:
            print("\nPress Ctrl+C to stop...")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if a9g:
            a9g.stop()

if __name__ == "__main__":
    main()
