import RPi.GPIO as GPIO
import time

class LightSensor:
    def __init__(self, digital_pin=17):
        """Initialize HW-072 light sensor.
        
        Args:
            digital_pin: GPIO pin for digital input (default: 17)
        """
        self.digital_pin = digital_pin
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.digital_pin, GPIO.IN)
        
        # Light threshold is built into the sensor's potentiometer
        # Adjust the sensor's sensitivity using the onboard potentiometer
    
    def read_light_level(self):
        """Read light level from sensor.
        
        Returns:
            str: 'Dark' or 'Bright' based on sensor reading
        """
        # HW-072 outputs digital signal (0 or 1)
        # When light level is below threshold (dark): output is HIGH (1)
        # When light level is above threshold (bright): output is LOW (0)
        is_dark = GPIO.input(self.digital_pin)
        
        return "Dark" if is_dark else "Bright"
    
    def cleanup(self):
        """Clean up GPIO."""
        pass  # No cleanup needed for input-only pin

def main():
    """Test the light sensor."""
    try:
        sensor = LightSensor()
        print("HW-072 Light Sensor Test")
        print("Press Ctrl+C to exit")
        
        while True:
            light_status = sensor.read_light_level()
            print(f"\nLight Level: {light_status}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if 'sensor' in locals():
            sensor.cleanup()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
