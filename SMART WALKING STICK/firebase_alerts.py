# -*- coding: utf-8 -*-

import time
import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

class FirebaseAlerts:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseAlerts, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not FirebaseAlerts._initialized:
            try:
                # Get the absolute path to the credentials file
                current_dir = os.path.dirname(os.path.abspath(__file__))
                cred_path = os.path.join(current_dir, 'walking-stick-app-firebase-adminsdk-fbsvc-3c09a7dcb7.json')
                
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"Firebase credentials file not found at {cred_path}")
                
                # Initialize Firebase connection only if not already initialized
                if not firebase_admin._apps:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': 'https://walking-stick-app-default-rtdb.firebaseio.com/'
                    })
                
                # Create references to different paths
                self.alerts_ref = db.reference('alerts')
                self.environment_ref = db.reference('environment')
                self.location_ref = db.reference('location')
                print("✓ Firebase connection initialized successfully")
                
                # Create initial alert nodes if they don't exist
                initial_data = {'initialized': int(time.time())}
                for node in ['fall', 'obstacle']:
                    current = self.alerts_ref.child(node).get()
                    if not current:
                        self.alerts_ref.child(node).set(initial_data)
                
                FirebaseAlerts._initialized = True
            
            except Exception as e:
                print(f"✗ Error initializing Firebase: {e}")
                raise
        
    def send_fall_alert(self, acceleration, location_data=None):
        """Send fall detection alert with location."""
        try:
            alert_data = {
                'type': 'FALL ALERT',
                'acceleration': acceleration,
                'timestamp': int(time.time())  # Use integer timestamp
            }
            if location_data and location_data['valid']:
                alert_data.update({
                    'latitude': location_data['latitude'],
                    'longitude': location_data['longitude'],
                    'altitude': location_data['altitude'],
                    'location_timestamp': int(location_data['timestamp']),
                    'location_cached': location_data.get('cached', False)
                })
            # Generate a unique key based on timestamp
            alert_key = f"fall_{int(time.time())}"
            self.alerts_ref.child('fall').child(alert_key).set(alert_data)
        except Exception as e:
            print(f"Error sending fall alert: {e}")
        
    def send_obstacle_alert(self, distance, location_data=None):
        """Send obstacle detection alert with location."""
        try:
            alert_data = {
                'type': 'OBSTACLE ALERT',
                'distance': float(distance),  # Ensure numeric value
                'timestamp': int(time.time())
            }
            if location_data and location_data['valid']:
                alert_data.update({
                    'latitude': location_data['latitude'],
                    'longitude': location_data['longitude'],
                    'altitude': location_data['altitude'],
                    'location_timestamp': int(location_data['timestamp']),
                    'location_cached': location_data.get('cached', False)
                })
            # Generate a unique key based on timestamp
            alert_key = f"obstacle_{int(time.time())}"
            self.alerts_ref.child('obstacle').child(alert_key).set(alert_data)
        except Exception as e:
            print(f"Error sending obstacle alert: {e}")
        
    def send_environment_alert(self, temp, humidity, light_level, location=None, detected_objects=None):
        """Send environment update with location."""
        try:
            alert_data = {
                'type': 'ENVIRONMENT UPDATE',
                'temperature': float(temp) if temp is not None else None,
                'humidity': float(humidity) if humidity is not None else None,
                'light_level': light_level,
                'timestamp': int(time.time())
            }
            if location and location['valid']:
                alert_data.update({
                    'latitude': location['latitude'],
                    'longitude': location['longitude'],
                    'altitude': location['altitude'],
                    'location_timestamp': int(location['timestamp']),
                    'location_cached': location.get('cached', False)
                })
            if detected_objects:
                alert_data['detected_objects'] = detected_objects
                
            # Use timestamp-based key for environment updates
            update_key = f"env_{int(time.time())}"
            self.environment_ref.child(update_key).set(alert_data)
        except Exception as e:
            print(f"Error sending environment alert: {e}")
        
    def send_location_update(self, location_data):
        """Send location update."""
        try:
            if location_data['valid']:
                update_data = {
                    'type': 'LOCATION UPDATE',
                    'latitude': float(location_data['latitude']),
                    'longitude': float(location_data['longitude']),
                    'altitude': float(location_data['altitude']),
                    'speed': float(location_data.get('speed', 0)),
                    'timestamp': int(time.time()),
                    'cached': bool(location_data.get('cached', False))
                }
                # Update current location
                self.location_ref.child('current').set(update_data)
                
                # Add to history with timestamp-based key
                history_key = f"loc_{int(time.time())}"
                self.location_ref.child('history').child(history_key).set(update_data)
        except Exception as e:
            print(f"Error sending location update: {e}")
        
    def send_emergency_location(self, location_data, alert_type):
        """Send emergency location update with alert type."""
        try:
            if location_data['valid']:
                alert_data = {
                    'type': f'EMERGENCY - {alert_type.upper()}',
                    'latitude': location_data['latitude'],
                    'longitude': location_data['longitude'],
                    'altitude': location_data['altitude'],
                    'speed': location_data.get('speed', 0),
                    'timestamp': location_data['timestamp'],
                    'cached': location_data.get('cached', False)
                }
                self.db.child('alerts').child('emergency').push(alert_data)
        except Exception as e:
            print(f"Error sending emergency location: {e}")
        
    def send_system_alert(self, alert_type, message=None):
        """Send system status alert to Firebase."""
        try:
            alert_data = {
                'type': alert_type,
                'message': message if message else alert_type,
                'timestamp': int(time.time())
            }
            # Use timestamp-based key for system alerts
            alert_key = f"sys_{int(time.time())}"
            self.db.child('system').child('alerts').child(alert_key).set(alert_data)
            print(f"System alert sent: {alert_type}")
            return True
        except Exception as e:
            print(f"Error sending system alert: {e}")
            return False
        
    def test_connection(self):
        """Test Firebase connection by writing and reading test data."""
        try:
            # Write test data
            test_data = {
                'test_timestamp': int(time.time()),
                'message': 'Test connection successful'
            }
            self.alerts_ref.child('test').set(test_data)
            
            # Read back test data
            read_data = self.alerts_ref.child('test').get()
            
            if read_data and read_data.get('message') == 'Test connection successful':
                print("✅ Firebase connection test successful!")
                print(f"Written data: {test_data}")
                print(f"Read data: {read_data}")
                return True
            else:
                print("❌ Firebase connection test failed - data mismatch")
                return False
                
        except Exception as e:
            print(f"❌ Firebase connection test failed: {e}")
            return False
