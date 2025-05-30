import smbus
import math
import time

class MPU6050:
    def __init__(self, bus=1, device_address=0x68):
        """Initialize MPU6050 sensor.
        
        Args:
            bus: I2C bus number (default: 1)
            device_address: MPU6050 I2C address (default: 0x68)
        """
        # MPU6050 Registers
        self.PWR_MGMT_1 = 0x6B
        self.SMPLRT_DIV = 0x19
        self.CONFIG = 0x1A
        self.GYRO_CONFIG = 0x1B
        self.ACCEL_CONFIG = 0x1C
        self.ACCEL_XOUT_H = 0x3B
        
        # Initialize I2C bus
        self.bus = smbus.SMBus(bus)
        self.device_address = device_address
        
        # Wake up the MPU6050
        self.bus.write_byte_data(self.device_address, self.PWR_MGMT_1, 0)
        
        # Configure the accelerometer (+/- 8g)
        self.bus.write_byte_data(self.device_address, self.ACCEL_CONFIG, 0x10)
        
        # Fall detection parameters
        self.FALL_THRESHOLD = 2.5  # 2.5g threshold for fall detection
        self.last_fall_time = 0
        self.MIN_FALL_INTERVAL = 3  # Minimum seconds between fall detections
        
    def read_raw_data(self, addr):
        """Read raw 16-bit value from MPU6050."""
        high = self.bus.read_byte_data(self.device_address, addr)
        low = self.bus.read_byte_data(self.device_address, addr + 1)
        
        value = ((high << 8) | low)
        if value > 32768:
            value = value - 65536
        return value
        
    def get_acceleration(self):
        """Get acceleration in g's."""
        # Read accelerometer raw values
        acc_x = self.read_raw_data(self.ACCEL_XOUT_H)
        acc_y = self.read_raw_data(self.ACCEL_XOUT_H + 2)
        acc_z = self.read_raw_data(self.ACCEL_XOUT_H + 4)
        
        # Convert to g's (1g = 4096 LSB for +/- 8g range)
        ax = acc_x / 4096.0
        ay = acc_y / 4096.0
        az = acc_z / 4096.0
        
        # Calculate total acceleration magnitude
        total_accel = math.sqrt(ax*ax + ay*ay + az*az)
        
        return {
            'x': round(ax, 3),
            'y': round(ay, 3),
            'z': round(az, 3),
            'total': round(total_accel, 3)
        }
        
    def detect_fall(self):
        """Detect if a fall has occurred based on acceleration."""
        accel = self.get_acceleration()
        current_time = time.time()
        
        # Check if acceleration magnitude exceeds threshold
        if accel['total'] > self.FALL_THRESHOLD:
            # Check if enough time has passed since last fall
            if current_time - self.last_fall_time > self.MIN_FALL_INTERVAL:
                self.last_fall_time = current_time
                return True, accel
        
        return False, accel

def main():
    try:
        # Initialize MPU6050
        mpu = MPU6050()
        print("MPU6050 Fall Detection Test")
        print("Press Ctrl+C to exit")
        print("\nAcceleration values in g's (1g = 9.81 m/s²)")
        print("Fall threshold set to 2.5g")
        
        while True:
            # Check for falls and get acceleration
            fall_detected, accel = mpu.detect_fall()
            
            if fall_detected:
                print("\n🚨 FALL DETECTED! 🚨")
                print(f"Total Acceleration: {accel['total']}g")
            
            # Print acceleration values every 10 seconds
            print(f"\nAcceleration (g):")
            print(f"X: {accel['x']:>6.3f}")
            print(f"Y: {accel['y']:>6.3f}")
            print(f"Z: {accel['z']:>6.3f}")
            print(f"Total: {accel['total']:>6.3f}")
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
