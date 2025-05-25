import threading
import time
from test_ultrasonic import UltrasonicSensor
from test_mpu6050 import MPU6050
from test_light_sensor import LightSensor
import RPi.GPIO as GPIO

class SensorMonitor:
    def __init__(self):
        try:
            self.ultrasonic = UltrasonicSensor()
            self.mpu = MPU6050()
            self.light_sensor = LightSensor()
            self.running = True
            
            # Create threads
            self.ultrasonic_thread = threading.Thread(target=self.monitor_distance)
            self.mpu_thread = threading.Thread(target=self.monitor_acceleration)
            self.light_thread = threading.Thread(target=self.monitor_light)
            
            # Set as daemon threads so they'll stop when main program stops
            self.ultrasonic_thread.daemon = True
            self.mpu_thread.daemon = True
            self.light_thread.daemon = True
            
        except Exception as e:
            print(f"Error initializing sensors: {e}")
            raise
    
    def monitor_distance(self):
        """Monitor distance from ultrasonic sensor."""
        while self.running:
            try:
                distance = self.ultrasonic.measure_distance()
                if distance is not None:
                    print(f"\nUltrasonic - Distance: {distance} cm")
                else:
                    print("\nUltrasonic - Error measuring distance")
                time.sleep(20)  # Measure every 20 seconds
            except Exception as e:
                print(f"Ultrasonic sensor error: {e}")
                time.sleep(1)
    
    def monitor_acceleration(self):
        """Monitor acceleration and detect falls."""
        while self.running:
            try:
                fall_detected, accel = self.mpu.detect_fall()
                
                if fall_detected:
                    print("\n🚨 FALL DETECTED! 🚨")
                    print(f"Total Acceleration: {accel['total']}g")
                
                print(f"\nMPU6050 - Acceleration (g):")
                print(f"X: {accel['x']:>6.3f}")
                print(f"Y: {accel['y']:>6.3f}")
                print(f"Z: {accel['z']:>6.3f}")
                print(f"Total: {accel['total']:>6.3f}")
                
                time.sleep(10)  # Measure every 10 seconds
            except Exception as e:
                print(f"MPU6050 sensor error: {e}")
                time.sleep(1)
    
    def monitor_light(self):
        """Monitor light levels."""
        while self.running:
            try:
                light_status = self.light_sensor.read_light_level()
                print(f"\nLight Sensor:")
                print(f"Light Level: {light_status}")
                time.sleep(1)  # Check light level every second
            except Exception as e:
                print(f"Light sensor error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start monitoring sensors."""
        print("Starting sensor monitoring...")
        print("Press Ctrl+C to exit")
        
        # Start threads
        self.ultrasonic_thread.start()
        self.mpu_thread.start()
        self.light_thread.start()
    
    def stop(self):
        """Stop monitoring and cleanup."""
        print("\nStopping sensor monitoring...")
        self.running = False
        
        # Wait for threads to finish
        self.ultrasonic_thread.join(timeout=1)
        self.mpu_thread.join(timeout=1)
        self.light_thread.join(timeout=1)
        
        # Cleanup all sensors
        self.ultrasonic.cleanup()
        self.light_sensor.cleanup()
        GPIO.cleanup()  # Final cleanup of GPIO

def main():
    monitor = None
    try:
        # Initialize and start monitoring
        monitor = SensorMonitor()
        monitor.start()
        
        # Keep main thread running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if monitor:
            monitor.stop()

if __name__ == "__main__":
    main()
