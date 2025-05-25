import RPi.GPIO as GPIO
import time

class UltrasonicSensor:
    def __init__(self, trigger_pin=23, echo_pin=24):
        """Initialize the HY-SRF05 sensor.
        
        Args:
            trigger_pin: GPIO pin for trigger (default: 23, GPIO23)
            echo_pin: GPIO pin for echo (default: 24, GPIO24)
        """
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        
        # Ensure trigger is low
        GPIO.output(self.trigger_pin, False)
        time.sleep(0.5)  # Wait for sensor to settle
        
    def measure_distance(self):
        """Measure distance in centimeters."""
        # Send 10us pulse to trigger
        GPIO.output(self.trigger_pin, True)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(self.trigger_pin, False)
        
        pulse_start = time.time()
        timeout = pulse_start + 1  # 1 second timeout
        
        # Wait for echo to go high
        while GPIO.input(self.echo_pin) == 0:
            pulse_start = time.time()
            if pulse_start > timeout:
                return None
            
        pulse_end = time.time()
        timeout = pulse_end + 1  # 1 second timeout
        
        # Wait for echo to go low
        while GPIO.input(self.echo_pin) == 1:
            pulse_end = time.time()
            if pulse_end > timeout:
                return None
        
        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150  # Speed of sound = 343m/s
        distance = round(distance, 2)
        
        return distance if 2 <= distance <= 450 else None  # Valid range: 2cm to 4.5m
        
    def cleanup(self):
        """Clean up GPIO."""
        GPIO.cleanup()

def main():
    try:
        # Create sensor instance
        sensor = UltrasonicSensor()
        print("HY-SRF05 Ultrasonic Sensor Test")
        print("Press Ctrl+C to exit")
        
        while True:
            distance = sensor.measure_distance()
            if distance is not None:
                print(f"\nDistance: {distance} cm")
            else:
                print("\nError measuring distance")
            
            time.sleep(20)  # Wait 20 seconds before next measurement
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if 'sensor' in locals():
            sensor.cleanup()

if __name__ == "__main__":
    main()
