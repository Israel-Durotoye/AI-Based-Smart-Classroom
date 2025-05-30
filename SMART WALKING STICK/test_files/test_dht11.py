# -*- coding: utf-8 -*-

import time
import adafruit_dht
import board

class DHT11Sensor:
    def __init__(self, pin=board.D4):
        self.pin = pin
        try:
            print("Initializing DHT11 sensor...")
            self.device = adafruit_dht.DHT11(self.pin)
            print(f"DHT11 sensor initialized on pin {pin}")
        except Exception as e:
            print(f"Error initializing DHT11: {e}")
            raise

    def read_sensor(self):
        try:
            temperature = self.device.temperature
            humidity = self.device.humidity
            if temperature is None or humidity is None:
                raise RuntimeError("Sensor returned None value")
            return temperature, humidity
        except RuntimeError as e:
            # Known intermittent errors reading sensor, can retry or just warn here
            print(f"Warning: Sensor read error: {e}")
            return None, None
        except Exception as e:
            print(f"Unexpected error reading sensor: {e}")
            return None, None

    def get_weather_description(self):
        temp, humidity = self.read_sensor()
        if temp is None or humidity is None:
            return "I'm having trouble reading the weather conditions."

        if temp < 15:
            temp_desc = "It's quite cold"
        elif temp < 20:
            temp_desc = "It's cool"
        elif temp < 25:
            temp_desc = "It's comfortable"
        elif temp < 30:
            temp_desc = "It's warm"
        else:
            temp_desc = "It's hot"

        if humidity < 30:
            humid_desc = "and very dry"
        elif humidity < 50:
            humid_desc = "with comfortable humidity"
        elif humidity < 70:
            humid_desc = "and somewhat humid"
        else:
            humid_desc = "and very humid"

        return f"{temp_desc} {humid_desc}. The temperature is {temp:.1f}\u00b0C with {humidity:.1f}% humidity."

    def cleanup(self):
        try:
            self.device.deinit()
        except AttributeError:
            # deinit may not exist; ignore
            pass

def main():
    sensor = DHT11Sensor()
    print("DHT11 Temperature and Humidity Sensor Test")
    print("Press Ctrl+C to exit\n")

    try:
        while True:
            temperature, humidity = sensor.read_sensor()

            if temperature is not None and humidity is not None:
                print(f"Temperature: {temperature:.1f} \u00b0C")
                print(f"Humidity: {humidity:.1f} %")
                print(sensor.get_weather_description(), "\n")
            else:
                print("Failed to read sensor. Check wiring.\n")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        sensor.cleanup()

if __name__ == "__main__":
    main()
