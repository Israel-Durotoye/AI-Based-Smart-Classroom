#!/usr/bin/env python3
import time
import sys

def test_firebase():
    try:
        from firebase_alerts import FirebaseAlerts
        firebase = FirebaseAlerts()
        print("✓ Firebase connection successful")
        return True
    except Exception as e:
        print(f"✗ Firebase test failed: {e}")
        return False

def test_audio():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print("\nAudio Devices:")
        print("-------------")
        for i, dev in enumerate(devices):
            print(f"{i}: {dev['name']}")
        print("\n✓ Audio system accessible")
        return True
    except Exception as e:
        print(f"✗ Audio test failed: {e}")
        return False

def test_camera():
    try:
        from camera_monitor import CameraMonitor
        camera = CameraMonitor()
        if camera.start():
            print("✓ Camera initialized successfully")
            camera.stop()
            return True
        else:
            print("✗ Camera initialization failed")
            return False
    except Exception as e:
        print(f"✗ Camera test failed: {e}")
        return False

def test_sensors():
    try:
        from test_ultrasonic import UltrasonicSensor
        from test_mpu6050 import MPU6050
        from test_light_sensor import LightSensor
        from test_dht11 import DHT11Sensor
        
        print("\nTesting sensors...")
        ultrasonic = UltrasonicSensor()
        print("✓ Ultrasonic sensor initialized")
        
        mpu = MPU6050()
        print("✓ MPU6050 initialized")
        
        light = LightSensor()
        print("✓ Light sensor initialized")
        
        dht11 = DHT11Sensor()
        print("✓ DHT11 sensor initialized")
        
        # Test readings
        dist = ultrasonic.measure_distance()
        print(f"Distance: {dist:.1f}cm")
        
        accel = mpu.read_accelerometer()
        print(f"Acceleration: X={accel['x']:.2f}, Y={accel['y']:.2f}, Z={accel['z']:.2f}")
        
        light_level = light.read_light_level()
        print(f"Light level: {light_level}")
        
        temp, humid = dht11.read_sensor()
        if temp is not None and humid is not None:
            print(f"Temperature: {temp:.1f}°C, Humidity: {humid:.1f}%")
        
        return True
    except Exception as e:
        print(f"✗ Sensor test failed: {e}")
        return False

def main():
    print("Component Testing Utility")
    print("========================")
    
    tests = {
        '1': ('Firebase Connection', test_firebase),
        '2': ('Audio System', test_audio),
        '3': ('Camera System', test_camera),
        '4': ('Sensors', test_sensors),
        'all': ('All Components', None)
    }
    
    while True:
        print("\nAvailable tests:")
        for key, (name, _) in tests.items():
            print(f"{key}: Test {name}")
        print("q: Quit")
        
        choice = input("\nSelect test to run: ").lower()
        
        if choice == 'q':
            break
        elif choice in tests:
            if choice == 'all':
                for _, (name, test_func) in tests.items():
                    if test_func:
                        print(f"\nTesting {name}...")
                        test_func()
            else:
                name, test_func = tests[choice]
                print(f"\nTesting {name}...")
                test_func()
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
