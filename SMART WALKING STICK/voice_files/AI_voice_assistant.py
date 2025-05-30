import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import queue
import time
from datetime import datetime
import RPi.GPIO as GPIO
from google.cloud import speech_v1
from google.cloud import texttospeech
from test_ultrasonic import UltrasonicSensor
from test_mpu6050 import MPU6050
from test_light_sensor import LightSensor
from test_dht11 import DHT11Sensor
from a9g_module import A9GModule
from test_object_detection import ObjectDetector
from voice_chat_model import VoiceChatModel
import os
import json

class VoiceAssistant:
    def __init__(self, button_pin=18, sample_rate=16000):
        """Initialize voice assistant with sensors and voice processing.
        
        Args:
            button_pin: GPIO pin for push-to-talk button (default: 18)
            sample_rate: Audio sample rate in Hz (default: 16000)
        """
        # Load audio device configuration
        try:
            with open('audio_config.json', 'r') as f:
                config = json.load(f)
                self.audio_device = config['device_id']
                print(f"Using audio device: {sd.query_devices(self.audio_device)['name']}")
        except:
            print("No audio configuration found, using default device")
            self.audio_device = None
            
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.button_pin = button_pin
        
        # Audio settings
        self.sample_rate = sample_rate
        self.audio_queue = queue.Queue()
        self.recording = False
        
        # Initialize Google Cloud clients
        self.speech_client = speech_v1.SpeechClient()
        self.tts_client = texttospeech.TextToSpeechClient()
        
        try:
            # Initialize sensors
            self.ultrasonic = UltrasonicSensor()
            self.mpu = MPU6050()
            self.light_sensor = LightSensor()
            self.dht11 = DHT11Sensor()  # Add DHT11 sensor
            self.gps_module = A9GModule()
            self.object_detector = ObjectDetector()
            
            print("All sensors initialized successfully")
            
            # Start sensor monitoring threads
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_sensors)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
        except Exception as e:
            print(f"Error initializing sensors: {e}")
            self.cleanup()
            raise
        
        # Initialize chat model
        try:
            self.chat_model = VoiceChatModel('voice_chat_model')
            print("Voice chat model loaded successfully")
        except Exception as e:
            print(f"Error loading voice chat model: {e}")
            self.chat_model = None
            
        # Add personality responses
        self.greetings = [
            "Hello! I'm your AI walking companion.",
            "Hi there! Ready to explore the world together?",
            "Greetings! Your smart walking stick is at your service.",
            "Hello friend! Let's make our journey safer together."
        ]
        self.acknowledgments = [
            "I'm on it!",
            "Let me check that for you.",
            "Right away!",
            "Consider it done.",
            "I'll help you with that."
        ]
        self.encouragements = [
            "You're doing great!",
            "We're making good progress.",
            "Stay confident, I'm here to help.",
            "You've got this, and I've got your back!"
        ]            # Initialize environmental context tracking
            self.last_light_level = "Normal"
            
            # Start voice assistant
            self._setup_commands()
            print("Voice assistant ready")
            self.speak(np.random.choice(self.greetings))
        
    def _setup_commands(self):
        """Setup voice command handlers"""
        self.commands = {
            "distance": self._handle_distance,
            "obstacles": self._handle_obstacles,
            "location": self._handle_location,
            "light": self._handle_light,
            "fall": self._handle_fall_status,
            "weather": self._handle_weather,  # Add weather command
            "temperature": self._handle_weather,  # Alternative command
            "help": self._handle_help,
            "stop": self._handle_stop
        }
        
    def _monitor_sensors(self):
        """Continuously monitor sensor data for alerts with smart context awareness"""
        last_alerts = {
            'fall': 0,
            'obstacle': 0,
            'object': 0,
            'light': 0
        }
        alert_cooldowns = {
            'fall': 30,  # 30 sec cooldown for fall alerts
            'obstacle': 5,  # 5 sec for obstacles
            'object': 10,  # 10 sec for object detection
            'light': 60   # 60 sec for light level changes
        }
        
        while self.monitoring:
            try:
                current_time = time.time()
                
                # Check for falls with improved context
                fall_detected, accel_data = self.mpu.detect_fall()
                if fall_detected and (current_time - last_alerts['fall']) > alert_cooldowns['fall']:
                    total_g = accel_data['total']
                    severity = "severe" if total_g > 3 else "possible"
                    self.speak(f"{severity.capitalize()} fall detected! Sending alert...")
                    self._send_alert("FALL DETECTED", 
                                   f"{severity.capitalize()} fall detected with acceleration: {total_g:.1f}g")
                    last_alerts['fall'] = current_time
                
                # Smart obstacle detection with context
                distance = self.ultrasonic.measure_distance()
                if distance and distance < 100 and (current_time - last_alerts['obstacle']) > alert_cooldowns['obstacle']:
                    if distance < 30:
                        self.speak("Warning! Very close obstacle ahead!")
                    elif distance < 50:
                        self.speak(f"Caution! Obstacle at {int(distance)} centimeters")
                    elif distance < 100:
                        # Only alert for obstacles between 50-100cm if moving (check accelerometer)
                        if abs(accel_data.get('x', 0)) > 0.2 or abs(accel_data.get('y', 0)) > 0.2:
                            self.speak(f"Note: Object {int(distance)} centimeters ahead")
                    last_alerts['obstacle'] = current_time
                
                # Enhanced object detection with prioritization
                frame, detections = self.object_detector.get_detections()
                if detections and (current_time - last_alerts['object']) > alert_cooldowns['object']:
                    # Prioritize important objects
                    priority_objects = ['person', 'car', 'bicycle', 'dog', 'chair', 'stairs']
                    important_detections = []
                    
                    for det in detections:
                        if det['confidence'] > 0.7 and det['class'] in priority_objects:
                            important_detections.append(det)
                    
                    if important_detections:
                        objects_str = ", ".join(f"{det['class']}" for det in important_detections[:2])
                        if len(important_detections) > 2:
                            objects_str += " and others"
                        self.speak(f"Detected {objects_str} nearby")
                        last_alerts['object'] = current_time
                
                # Monitor light levels for significant changes
                light_level = self.light_sensor.read_light_level()
                if (current_time - last_alerts['light']) > alert_cooldowns['light']:
                    if light_level == "Dark" and self.last_light_level != "Dark":
                        self.speak("Light levels have decreased significantly. Please be extra careful.")
                    elif light_level == "Bright" and self.last_light_level == "Dark":
                        self.speak("Light levels have improved.")
                    self.last_light_level = light_level
                    last_alerts['light'] = current_time
                
                time.sleep(0.1)  # Reduced sleep time for more responsive monitoring
                
            except Exception as e:
                print(f"Error in sensor monitoring: {e}")
                time.sleep(1)
                
    def _record_audio(self):
        """Record audio while button is pressed"""
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            self.audio_queue.put(indata.copy())
            
        try:
            with sd.InputStream(samplerate=self.sample_rate, 
                              channels=1, 
                              callback=audio_callback,
                              device=self.audio_device):
                print("Listening... (Release button to stop)")
                while GPIO.input(self.button_pin) == GPIO.LOW:  # While button is pressed
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"Error recording audio: {e}")
            
    def transcribe_audio(self):
        """Convert recorded audio to text using Google Speech-to-Text"""
        # Combine all audio data
        audio_data = []
        while not self.audio_queue.empty():
            audio_data.append(self.audio_queue.get())
        
        if not audio_data:
            return None
            
        audio_data = np.concatenate(audio_data, axis=0)
        
        # Save as WAV file
        sf.write("temp.wav", audio_data, self.sample_rate)
        
        # Transcribe using Google Speech-to-Text
        try:
            with open("temp.wav", "rb") as audio_file:
                content = audio_file.read()
                
            audio = speech_v1.RecognitionAudio(content=content)
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code="en-US",
            )
            
            response = self.speech_client.recognize(config=config, audio=audio)
            
            for result in response.results:
                return result.alternatives[0].transcript
                
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            if os.path.exists("temp.wav"):
                os.remove("temp.wav")
                
    def speak(self, text):
        """Convert text to speech and play it"""
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Neural2-C",  # Use neural voice for better quality
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=1.0,
                pitch=0.0
            )
            
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Save and play audio
            with open("temp_speech.wav", "wb") as out:
                out.write(response.audio_content)
                
            data, fs = sf.read("temp_speech.wav", dtype='float32')
            sd.play(data, fs, device=self.audio_device)
            sd.wait()
            
        except Exception as e:
            print(f"Speech synthesis error: {e}")
        finally:
            if os.path.exists("temp_speech.wav"):
                os.remove("temp_speech.wav")
                
    def _send_alert(self, alert_type, message):
        """Send alert via SMS and update Firebase"""
        try:
            # Get current location
            location = self.gps_module.get_location()
            
            # Format alert message
            alert_msg = f"ALERT: {alert_type}\n{message}"
            if location.get('fix'):
                maps_link = f"https://maps.google.com/?q={location['latitude']},{location['longitude']}"
                alert_msg += f"\nLocation: {maps_link}"
            
            # Send SMS
            self.gps_module.send_sms(alert_msg)
            
        except Exception as e:
            print(f"Error sending alert: {e}")
            
    def _get_random_response(self, response_type):
        """Get a random response based on the type"""
        if response_type == 'greet':
            return np.random.choice(self.greetings)
        elif response_type == 'ack':
            return np.random.choice(self.acknowledgments)
        elif response_type == 'encourage':
            return np.random.choice(self.encouragements)
        return ""

    def _handle_distance(self):
        """Handle distance measurement command with personality"""
        self.speak(self._get_random_response('ack'))
        distance = self.ultrasonic.measure_distance()
        if distance:
            if distance < 30:
                self.speak(f"Careful! An obstacle is very close, just {int(distance)} centimeters away.")
            elif distance < 100:
                self.speak(f"There's an obstacle {int(distance)} centimeters ahead. We should proceed carefully.")
            else:
                self.speak(f"The path looks clear! Nearest obstacle is {int(distance)} centimeters away.")
        else:
            self.speak("Hmm, I'm having trouble measuring the distance. Let's try again in a moment.")

    def _handle_obstacles(self):
        """Handle obstacle detection command with enhanced context awareness"""
        try:
            self.speak(self._get_random_response('ack'))
            
            # Get distance measurement first
            distance = self.ultrasonic.measure_distance()
            distance_warning = ""
            if distance and distance < 100:
                distance_warning = f" at approximately {int(distance)} centimeters"
            
            # Get object detection results
            frame, detections = self.object_detector.get_detections()
            if detections:
                # Filter and sort detections by confidence and proximity
                relevant_detections = []
                priority_objects = {
                    "person": 1,
                    "car": 1,
                    "bicycle": 2,
                    "motorcycle": 2,
                    "dog": 2,
                    "stairs": 1,
                    "door": 2,
                    "chair": 3,
                    "bench": 3
                }
                
                for det in detections:
                    if det['confidence'] > 0.5:
                        priority = priority_objects.get(det['class'], 4)
                        relevant_detections.append((priority, det))
                
                # Sort by priority and confidence
                relevant_detections.sort(key=lambda x: (x[0], -x[1]['confidence']))
                
                if relevant_detections:
                    # Group detections by priority
                    current_priority = relevant_detections[0][0]
                    priority_group = []
                    
                    for priority, det in relevant_detections[:3]:  # Limit to top 3
                        if priority != current_priority:
                            break
                        priority_group.append(det)
                    
                    # Construct detailed message
                    objects_str = ", ".join(f"{det['class']}" for det in priority_group)
                    confidence_level = "high" if priority_group[0]['confidence'] > 0.8 else "moderate"
                    
                    self.speak(f"I detect {objects_str}{distance_warning} with {confidence_level} confidence.")
                    
                    # Provide relevant safety tips
                    safety_tips = {
                        "person": "There are people nearby. You may want to announce your presence.",
                        "car": "Moving vehicles detected. Please be extra cautious.",
                        "bicycle": "Watch for cyclists passing by.",
                        "motorcycle": "Be aware of motorcycles in the area.",
                        "dog": "There's a dog nearby. Stay calm and be cautious.",
                        "stairs": "Stairs detected. Take extra care with each step.",
                        "door": "There's a door ahead. Check if it's open or closed.",
                        "chair": "Seating is available if you need to rest.",
                        "bench": "There's a bench nearby if you need to rest."
                    }
                    
                    # Provide most relevant safety tip
                    primary_object = priority_group[0]['class']
                    if primary_object in safety_tips:
                        self.speak(safety_tips[primary_object])
            else:
                if distance_warning:
                    self.speak(f"I detect an obstacle{distance_warning}, but I can't identify what it is. Please proceed with caution.")
                else:
                    self.speak("The path appears clear, but let's stay alert!")
                    
        except Exception as e:
            self.speak("I'm having trouble with the object detection system. Please wait a moment and try again.")
            
    def _handle_light(self):
        """Handle light level query command with personality"""
        self.speak(self._get_random_response('ack'))
        light_status = self.light_sensor.read_light_level()
        responses = {
            "Dark": "It's quite dark here. Would you like me to be extra vigilant?",
            "Bright": "The lighting is good, making it easier for us to navigate!"
        }
        self.speak(responses.get(light_status, f"The current light level is {light_status}"))

    def _handle_weather(self):
        """Handle weather status command with enhanced context"""
        self.speak(self._get_random_response('ack'))
        try:
            temp, humidity = self.dht11.read_sensor()
            if temp is not None and humidity is not None:
                weather_desc = self.dht11.get_weather_description()
                time_context = "today" if 6 <= datetime.now().hour < 18 else "tonight"
                
                # Add relevant recommendations based on conditions
                if temp > 30:
                    weather_desc += " You may want to stay in cooler areas and stay hydrated."
                elif temp < 15:
                    weather_desc += " You might want to wear something warm."
                
                if humidity > 80:
                    weather_desc += " The high humidity might make it feel warmer."
                elif humidity < 30:
                    weather_desc += " The air is quite dry."
                    
                self.speak(f"The weather {time_context} is: {weather_desc}")
            else:
                self.speak("I'm having trouble reading the weather sensors. Please try again in a moment.")
        except Exception as e:
            self.speak("Sorry, I couldn't get the weather information right now. The sensors might need checking.")

    def _handle_fall_status(self):
        """Handle fall detection status command"""
        fall_detected, accel_data = self.mpu.detect_fall()
        if fall_detected:
            self.speak("Fall detected! Sending alert...")
            self._send_alert("FALL DETECTED", "Fall detected through voice command check")
        else:
            self.speak("No fall detected")
            
    def _handle_help(self):
        """Handle help command"""
        help_msg = ("Available commands: distance to obstacles, "
                   "detect obstacles, current location, weather conditions, "
                   "light level, check for falls, and stop monitoring")
        self.speak(help_msg)
        
    def _handle_stop(self):
        """Handle stop command"""
        self.speak("Stopping monitoring. It was a pleasure helping you!")
        self.monitoring = False
        
    def process_command(self, command):
        """Process voice command using chat model and specific handlers"""
        command = command.lower()
        
        # First try specific command handlers
        if "distance" in command or "how far" in command:
            self._handle_distance()
        elif "obstacles" in command or "detect" in command:
            self._handle_obstacles()
        elif "location" in command or "where" in command:
            self._handle_location()
        elif "weather" in command or "temperature" in command:
            self._handle_weather()
        elif "light" in command:
            self._handle_light()
        elif "fall" in command:
            self._handle_fall_status()
        elif "help" in command:
            self._handle_help()
        elif "stop" in command:
            self._handle_stop()
        else:
            # Extract keywords and try to infer intent
            keywords = command.lower().split()
            inferred_command = None
            
            # Look for close matches or synonyms
            distance_keywords = ["far", "away", "close", "near", "distance"]
            obstacle_keywords = ["see", "detect", "front", "ahead", "object"]
            weather_keywords = ["hot", "cold", "warm", "temperature", "humid"]
            light_keywords = ["bright", "dark", "lighting", "dim", "visibility"]
            
            if any(word in keywords for word in distance_keywords):
                inferred_command = "distance"
            elif any(word in keywords for word in obstacle_keywords):
                inferred_command = "obstacles"
            elif any(word in keywords for word in weather_keywords):
                inferred_command = "weather"
            elif any(word in keywords for word in light_keywords):
                inferred_command = "light"
                
            if inferred_command:
                self.speak(f"I think you're asking about {inferred_command}. Let me check that for you.")
                if inferred_command in self.commands:
                    self.commands[inferred_command]()
            else:
                # Use chat model for general conversation
                if self.chat_model:
                    response = self.chat_model.generate_response(command)
                    self.speak(response)
                else:
                    # Enhanced error with suggestions
                    self.speak("I'm not quite sure what you're asking. You can say things like:")
                    examples = [
                        "'how far are obstacles?'",
                        "'detect objects ahead'",
                        "'what's the weather like?'",
                        "'check the lighting'",
                        "or 'help' for more options"
                    ]
                    self.speak(" or ".join(examples))
            
    def run(self):
        """Main voice assistant loop"""
        print("Press and hold the button to speak a command")
        
        try:
            while True:
                if GPIO.input(self.button_pin) == GPIO.LOW:  # Button pressed
                    self.speak("Listening...")
                    self._record_audio()
                    
                    # Process recorded audio
                    text = self.transcribe_audio()
                    if text:
                        print(f"Recognized: {text}")
                        self.process_command(text)
                    else:
                        self.speak("Sorry, I didn't catch that")
                        
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping voice assistant...")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        self.monitoring = False
        if hasattr(self, 'ultrasonic'):
            self.ultrasonic.cleanup()
        if hasattr(self, 'gps_module'):
            self.gps_module.cleanup()
        GPIO.cleanup()

def main():
    try:
        assistant = VoiceAssistant()
        assistant.run()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()