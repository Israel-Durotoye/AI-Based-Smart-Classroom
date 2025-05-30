# -*- coding: utf-8 -*-

import threading
import time
import queue
import random
import pyttsx3
from test_ultrasonic import UltrasonicSensor
from test_mpu6050 import MPU6050
from test_light_sensor import LightSensor
from firebase_alerts import FirebaseAlerts
from a9g_module import A9GModule
from camera_monitor import CameraMonitor
import RPi.GPIO as GPIO
import adafruit_dht
import board

# Button pin configuration
BUTTON_PIN = 27  # GPIO27 (Pin 13)

class SpeechManager:
    def __init__(self):
        self.engine = pyttsx3.init()
        
        # Get available voices
        voices = self.engine.getProperty('voices')
        # Try to find a better quality voice
        for voice in voices:
            if "english" in voice.name.lower() and ("premium" in voice.name.lower() or "enhanced" in voice.name.lower()):
                self.engine.setProperty('voice', voice.id)
                break
        
        # Adjust voice properties for better quality
        self.engine.setProperty('rate', 150)  # Speed of speech
        self.engine.setProperty('volume', 0.9)  # Volume level
        
        self.speech_queue = queue.Queue()
        self.last_spoken = {}
        self.running = True
        self.speech_thread = threading.Thread(target=self._process_speech_queue)
        self.speech_thread.daemon = True
        self.speech_thread.start()
        
        # Fun jokes and facts
        self.jokes = [
            "Why don't blind people skydive? Because it scares their dogs!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why did the scarecrow win an award? Because he was outstanding in his field!",
            "What do you call a fake noodle? An impasta!",
            "Why did the cookie go to the doctor? Because it was feeling crumbly!",
            "What do you call a can opener that doesn't work? A can't opener!",
            "What did the grape say when it got stepped on? Nothing, it just let out a little wine!"
        ]
        
        self.fun_facts = [
            "The human brain can process images in as little as 13 milliseconds!",
            "Your sense of touch is so sensitive that you can feel objects as small as 13 nanometers!",
            "The average person spends 6 months of their lifetime waiting for red lights to turn green.",
            "Your brain generates enough electricity to power a small LED light.",
            "The human body contains enough carbon to make 900 pencils.",
            "Sound travels about four times faster in water than in air!",
            "A day on Venus is longer than its year!"
        ]
        
        self.random_prompts = [
            "Did you know that walking 30 minutes a day can improve your mood and health?",
            "Remember to stay hydrated throughout your day!",
            "Taking deep breaths can help you stay calm and focused.",
            "You're doing great! Keep moving forward.",
            "Safety first! Take your time to navigate carefully."
        ]
        
        self.last_joke_time = time.time()
        
    def speak(self, text, category='general', min_interval=5):
        """Add text to speech queue with category-based throttling."""
        current_time = time.time()
        if category not in self.last_spoken or \
           (current_time - self.last_spoken.get(category, 0)) >= min_interval:
            self.speech_queue.put(text)
            self.last_spoken[category] = current_time
            
    def maybe_tell_joke(self):
        """Tell a random joke every few minutes."""
        current_time = time.time()
        if current_time - self.last_joke_time > 300: # 5 minutes
            joke = random.choice(self.jokes)
            self.speak(joke, 'joke', min_interval=300)
            self.last_joke_time = current_time
            
    def get_random_prompt(self):
        """Generate a random prompt including weather, jokes, or facts."""
        # Define weights to control frequency of different prompt types
        choices = {
            'weather': 0.2,   # 20% chance for weather
            'joke': 0.3,      # 30% chance for jokes
            'fact': 0.3,      # 30% chance for facts
            'prompt': 0.2     # 20% chance for general prompts
        }
        
        prompt_type = random.choices(list(choices.keys()), list(choices.values()))[0]
        
        if prompt_type == 'weather':
            return None  # This will trigger weather reading in monitor_button
        elif prompt_type == 'joke':
            return random.choice(self.jokes)
        elif prompt_type == 'fact':
            return random.choice(self.fun_facts)
        else:
            return random.choice(self.random_prompts)

    def _process_speech_queue(self):
        """Process speech queue in background."""
        while self.running:
            try:
                if not self.speech_queue.empty():
                    text = self.speech_queue.get()
                    self.engine.say(text)
                    self.engine.runAndWait()
                time.sleep(0.1)
            except Exception as e:
                print(f"Speech error: {e}")
                time.sleep(1)
                
    def cleanup(self):
        """Clean up speech engine."""
        self.running = False
        self.speech_thread.join(timeout=1)

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
            print(f"Warning: DHT11 read error: {e}")
            return None, None
        except Exception as e:
            print(f"Unexpected DHT11 error: {e}")
            return None, None

    def get_weather_description(self, temp, humidity):
        if temp is None or humidity is None:
            return "Unable to determine weather conditions"

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

        return f"{temp_desc} {humid_desc}"

    def cleanup(self):
        try:
            self.device.deinit()
            print("DHT11 sensor cleaned up")
        except AttributeError:
            pass

class SensorMonitor:
    def __init__(self):
        try:
            # Initialize GPIO for button
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            self.ultrasonic = UltrasonicSensor()
            self.mpu = MPU6050()
            self.light_sensor = LightSensor()
            self.dht11 = DHT11Sensor()
            self.speech = SpeechManager()
            self.firebase = FirebaseAlerts()
            self.gps = A9GModule()
            self.camera = CameraMonitor()
            
            self.running = True
            self.last_fall_alert = 0
            self.fall_reminder_count = 0
            self.last_button_press = 0
            self.last_env_alert = 0
            self.last_location_update = 0
            self.last_network_check = 0
            self.last_camera_announce = 0
            
            # Initialize GPS and camera
            print("\nInitializing GPS/GSM module and camera...")
            
            # Initialize GPS first
            gps_success = False
            retry_count = 0
            while not gps_success and retry_count < 3:
                if self.gps.init_module():
                    print("GPS/GSM module initialized successfully")
                    gps_success = True
                    self.gps.start_monitoring()
                    print("Waiting for GPS fix...")
                    for _ in range(30):
                        location = self.gps.get_location(use_cached=False)
                        if location['valid']:
                            print(f"Initial GPS fix obtained: {location['latitude']:.6f}, {location['longitude']:.6f}")
                            break
                        time.sleep(1)
                else:
                    retry_count += 1
                    print(f"Retry {retry_count}/3: Failed to initialize GPS/GSM module")
                    time.sleep(2)

            # Initialize camera
            if self.camera.start():
                print("Camera initialized successfully")
                self.speech.speak("Camera system initialized. I can now help you identify objects in your surroundings.", 'system')
            else:
                print("Warning: Failed to initialize camera")
                self.speech.speak("Warning: Camera initialization failed. Object detection will not be available.", 'error')
            
            # Check network status
            if self.gps.check_network_status():
                print("GSM network registered successfully")
                signal = self.gps.check_signal_strength()
                print(f"Signal strength: {signal}")
            else:
                print("Warning: No GSM network registration")
                self.speech.speak("Warning: No cellular network connection. Emergency alerts may not work properly.", 'error')

            # Create threads
            self.ultrasonic_thread = threading.Thread(target=self.monitor_distance)
            self.mpu_thread = threading.Thread(target=self.monitor_acceleration)
            self.light_thread = threading.Thread(target=self.monitor_light)
            self.dht11_thread = threading.Thread(target=self.monitor_temperature)
            self.button_thread = threading.Thread(target=self.monitor_button)
            self.location_thread = threading.Thread(target=self.monitor_location)
            self.network_thread = threading.Thread(target=self.monitor_network)
            self.camera_thread = threading.Thread(target=self.monitor_camera)
            
            # Set as daemon threads
            self.ultrasonic_thread.daemon = True
            self.mpu_thread.daemon = True
            self.light_thread.daemon = True
            self.dht11_thread.daemon = True
            self.button_thread.daemon = True
            self.location_thread.daemon = True
            self.network_thread.daemon = True
            self.camera_thread.daemon = True
            
        except Exception as e:
            print(f"Error initializing sensors: {e}")
            raise
    
    def monitor_distance(self):
        """Monitor distance from ultrasonic sensor."""
        last_speak_time = 0
        while self.running:
            try:
                distance = self.ultrasonic.measure_distance()
                current_time = time.time()
                
                if distance is not None:
                    print(f"\nUltrasonic - Distance: {distance} cm")
                    
                    # Speak if obstacle is within 50cm and it's been 30 seconds
                    if distance <= 50 and (current_time - last_speak_time) >= 30:
                        message = f"There is an obstacle {int(distance)} centimeters ahead of you"
                        self.speech.speak(message, 'obstacle', min_interval=30)
                        
                        # Get location data for alert
                        location_data = self.gps.get_location()
                        self.firebase.send_obstacle_alert(distance, location_data)
                        last_speak_time = current_time
                else:
                    print("\nUltrasonic - Error measuring distance")
                    
                time.sleep(1)
            except Exception as e:
                print(f"Ultrasonic sensor error: {e}")
                time.sleep(1)
    
    def monitor_acceleration(self):
        """Monitor acceleration and detect falls."""
        while self.running:
            try:
                fall_detected, accel = self.mpu.detect_fall()
                current_time = time.time()
                
                if fall_detected:
                    print("\n🚨 FALL DETECTED! 🚨")
                    print(f"Total Acceleration: {accel['total']}g")
                    
                    # Get location for emergency alert
                    location_data = self.gps.get_location()
                    
                    # Send fall alert to Firebase with location
                    self.firebase.send_fall_alert(accel['total'])
                    if location_data['valid']:
                        self.firebase.send_emergency_location(location_data, "fall_detected")
                        
                        # Send emergency SMS
                        if self.gps.send_emergency_sms("FALL DETECTED", location_data):
                            print("Emergency SMS sent successfully")
                        else:
                            print("Failed to send emergency SMS")
                    
                    # Initial fall detection announcement
                    self.speech.speak("Fall detected! Emergency contacts are being notified.", 'fall', min_interval=5)
                    self.last_fall_alert = current_time
                    self.fall_reminder_count = 0
                elif self.last_fall_alert > 0:
                    # If stick hasn't been picked up (checking acceleration)
                    if accel['total'] < 1.2 and (current_time - self.last_fall_alert) >= 30:
                        reminders = [
                            "I'm right here!",
                            "Don't forget to pick me up!",
                            "Over here! I can help you navigate!"
                        ]
                        if self.fall_reminder_count < 5:  # Limit reminders
                            self.speech.speak(random.choice(reminders), 'fall_reminder', min_interval=30)
                            self.fall_reminder_count += 1
                
                print(f"\nMPU6050 - Acceleration (g):")
                print(f"X: {accel['x']:>6.3f}")
                print(f"Y: {accel['y']:>6.3f}")
                print(f"Z: {accel['z']:>6.3f}")
                print(f"Total: {accel['total']:>6.3f}")
                
                time.sleep(2)  # Check acceleration more frequently
            except Exception as e:
                print(f"MPU6050 sensor error: {e}")
                time.sleep(1)
    
    def monitor_light(self):
        """Monitor light levels."""
        last_speak_time = 0
        while self.running:
            try:
                light_status = self.light_sensor.read_light_level()
                current_time = time.time()
                
                print(f"\nLight Sensor:")
                print(f"Light Level: {light_status}")
                
                # Speak light level conditions every minute
                if current_time - last_speak_time >= 60:
                    if light_status == "Dark":
                        self.speech.speak(
                            "The room you're in is dark. Please turn on your flashlight for better environment analysis.",
                            'light',
                            min_interval=60
                        )
                    elif light_status == "Bright":
                        self.speech.speak(
                            "The room you're in is bright. Watch out for obstacles.",
                            'light',
                            min_interval=60
                        )
                    last_speak_time = current_time
                    
                time.sleep(1)
            except Exception as e:
                print(f"Light sensor error: {e}")
                time.sleep(1)
    
    def monitor_temperature(self):
        """Monitor temperature and humidity from DHT11 sensor."""
        last_speak_time = 0
        while self.running:
            try:
                temperature, humidity = self.dht11.read_sensor()
                current_time = time.time()
                
                if temperature is not None and humidity is not None:
                    print(f"\nDHT11 Sensor:")
                    print(f"Temperature: {temperature:.1f} \u00b0C")
                    print(f"Humidity: {humidity:.1f} %")
                    weather_desc = self.dht11.get_weather_description(temperature, humidity)
                    print(f"Conditions: {weather_desc}")
                    
                    # Speak weather conditions every 5 minutes
                    if current_time - last_speak_time >= 300:
                        message = f"The weather currently feels {weather_desc.lower()}. "
                        message += f"The temperature is {int(temperature)} degrees Celsius "
                        message += f"with {int(humidity)} percent humidity."
                        self.speech.speak(message, 'weather', min_interval=300)
                        last_speak_time = current_time
                        
                        # Maybe tell a joke after weather report
                        self.speech.maybe_tell_joke()
                        
                time.sleep(2)
            except Exception as e:
                print(f"DHT11 sensor error: {e}")
                time.sleep(2)

    def monitor_button(self):
        """Monitor button presses and trigger random prompts."""
        while self.running:
            try:
                # Button is pulled up, so we look for falling edge (button press)
                if not GPIO.input(BUTTON_PIN):
                    current_time = time.time()
                    # Debounce button and limit prompt frequency
                    if current_time - self.last_button_press >= 2:
                        print("\n🔘 Button pressed! Generating random prompt...")
                        self.last_button_press = current_time
                        prompt = self.speech.get_random_prompt()
                        
                        if prompt is None:  # Weather prompt requested
                            temperature, humidity = self.dht11.read_sensor()
                            if temperature is not None and humidity is not None:
                                weather_desc = self.dht11.get_weather_description(temperature, humidity)
                                prompt = f"The weather currently feels {weather_desc.lower()}. "
                                prompt += f"The temperature is {int(temperature)} degrees Celsius "
                                prompt += f"with {int(humidity)} percent humidity."
                            else:
                                prompt = "I'm having trouble reading the weather conditions right now."
                        
                        self.speech.speak(prompt, 'button', min_interval=2)
                    time.sleep(0.1)  # Short sleep to prevent CPU overuse
                else:
                    time.sleep(0.05)  # Very short sleep while waiting for button press
                    
            except Exception as e:
                print(f"Button monitoring error: {e}")
                time.sleep(1)

    def monitor_environment(self):
        """Monitor and report environmental conditions."""
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_env_alert >= 300:  # Every 5 minutes
                    temperature, humidity = self.dht11.read_sensor()
                    light_status = self.light_sensor.read_light_level()
                    location_data = self.gps.get_location()
                    
                    if temperature is not None and humidity is not None:
                        self.firebase.send_environment_alert(
                            temp=temperature,
                            humidity=humidity,
                            light_level=light_status,
                            location=location_data
                        )
                        self.last_env_alert = current_time
                        
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Environment monitoring error: {e}")
                self.firebase.send_system_alert("Environment monitoring error", str(e))
                time.sleep(60)

    def monitor_location(self):
        """Monitor and update location data."""
        while self.running:
            try:
                current_time = time.time()
                
                # Update location every 60 seconds
                if current_time - self.last_location_update >= 60:
                    location_data = self.gps.get_location()
                    
                    if location_data['valid']:
                        # Format location message
                        message = self.gps.format_location_message(location_data, "LOCATION UPDATE")
                        print(f"\n{message}")
                        
                        # Send regular location update to Firebase
                        self.firebase.send_location_update(location_data)
                        self.last_location_update = current_time
                    
                time.sleep(5)
                
            except Exception as e:
                print(f"Location monitoring error: {e}")
                time.sleep(5)

    def monitor_network(self):
        """Monitor network status and signal strength."""
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_network_check >= 60:  # Check every minute
                    network_status = self.gps.check_network_status()
                    signal_strength = self.gps.check_signal_strength()
                    
                    if not network_status:
                        print("⚠️ No GSM network connection")
                        self.firebase.send_system_alert("GSM network connection lost")
                    elif signal_strength < 10:  # Weak signal
                        print(f"⚠️ Weak GSM signal: {signal_strength}")
                        self.firebase.send_system_alert(f"Weak GSM signal: {signal_strength}")
                    
                    self.last_network_check = current_time
                
                time.sleep(10)
            except Exception as e:
                print(f"Network monitoring error: {e}")
                time.sleep(10)

    def monitor_camera(self):
        """Monitor camera feed and announce detected objects."""
        while self.running:
            try:
                # Get object summary and announce if available
                summary = self.camera.get_object_summary()
                if summary:
                    current_time = time.time()
                    if current_time - self.last_camera_announce >= 10:  # Announce every 10 seconds max
                        self.speech.speak(summary, 'camera')
                        self.last_camera_announce = current_time
                        
                        # Get location for object detection alert
                        location_data = self.gps.get_location()
                        if location_data['valid']:
                            # Send to Firebase with detected objects and location
                            self.firebase.send_environment_alert(
                                temp=None,
                                humidity=None,
                                light_level="N/A",
                                location=location_data,
                                detected_objects=self.camera.detected_objects
                            )
                
                time.sleep(1)
            except Exception as e:
                print(f"Camera monitoring error: {e}")
                time.sleep(5)

    def start(self):
        """Start monitoring sensors."""
        print("Starting sensor monitoring...")
        print("Press Ctrl+C to exit")
        print("Press the button for random prompts and information!")
        
        # Initial greeting and system alert
        welcome_msg = "Smart walking stick system started"
        self.speech.speak("Hello! I'm your smart walking stick. I'll help you navigate and keep you informed about your surroundings. I can now detect objects using the camera. Press the button anytime for interesting facts and information!", 'greeting')
        self.firebase.send_system_alert(welcome_msg)
        
        # Start threads
        self.ultrasonic_thread.start()
        self.mpu_thread.start()
        self.light_thread.start()
        self.dht11_thread.start()
        self.button_thread.start()
        self.location_thread.start()
        self.network_thread.start()
        self.camera_thread.start()
        
    def stop(self):
        """Stop monitoring and cleanup."""
        print("\nStopping sensor monitoring...")
        self.running = False
        
        # Stop GPS and camera monitoring
        self.gps.stop_monitoring()
        self.camera.stop()
        
        # Farewell message and system alert
        goodbye_msg = "Smart walking stick system stopped"
        self.speech.speak("Goodbye! Take care and stay safe!", 'farewell')
        self.firebase.send_system_alert(goodbye_msg)
        
        # Wait for threads to finish
        self.ultrasonic_thread.join(timeout=1)
        self.mpu_thread.join(timeout=1)
        self.light_thread.join(timeout=1)
        self.dht11_thread.join(timeout=1)
        self.camera_thread.join(timeout=1)
        
        # Cleanup all sensors
        self.ultrasonic.cleanup()
        self.light_sensor.cleanup()
        self.dht11.cleanup()
        self.speech.cleanup()
        GPIO.cleanup()
