import RPi.GPIO as GPIO
import time
import json
import firebase_admin
from firebase_admin import credentials, db
# Import sensor modules
from test_mpu6050 import MPU6050
from test_ultrasonic import UltrasonicSensor
from test_object_detection import ObjectDetector
from a9g_module import A9GModule

# Initialize sensor objects
mpu6050_sensor = MPU6050()
ultrasonic_sensor = UltrasonicSensor()
camera_detector = ObjectDetector()
gps_gsm_module = A9GModule()

# --- Firebase Initialization (if not already done) ---
# Initialize Firebase with admin credentials
try:
    cred = credentials.Certificate("walking-stick-app-firebase-adminsdk-fbsvc-c9db4d30a3.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://walking-stick-app-default-rtdb.firebaseio.com'
    })
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    # Handle error, perhaps log or exit

# --- GPIO Setup for PTT Button ---
PTT_BUTTON_PIN = 17 # Example GPIO pin
GPIO.setmode(GPIO.BCM)
GPIO.setup(PTT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Pull-up resistor

# --- Voice Assistant Libraries (Placeholders) ---
# For STT (Speech-to-Text)
# Setup Google Cloud Speech-to-Text
from google.cloud import speech_v1p1beta1 as speech
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-services.json" # Using the Google Cloud credentials file

# For TTS (Text-to-Speech)
# Example using Google Cloud TTS:
from google.cloud import texttospeech

# For audio recording/playback
import sounddevice as sd
import soundfile as sf
import numpy as np

# --- Configuration ---
RECORD_DURATION = 5  # seconds for maximum recording duration
SAMPLE_RATE = 16000  # Hz, common for speech processing

# --- Google Cloud Clients ---
stt_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

def record_audio(duration=RECORD_DURATION, samplerate=SAMPLE_RATE):
    print("Listening...")
    # Record audio
    audio_data = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait() # Wait until recording is finished
    print("Recording finished.")
    return audio_data

def transcribe_audio(audio_data):
    # Convert numpy array to bytes for Google Cloud STT
    audio_content = audio_data.tobytes()

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="en-US", # Or the appropriate language for your user
    )

    try:
        response = stt_client.recognize(config=config, audio=audio)
        if response.results:
            transcript = response.results[0].alternatives[0].transcript
            print(f"User said: {transcript}")
            return transcript
        else:
            print("Could not understand audio.")
            return ""
    except Exception as e:
        print(f"Google STT Error: {e}")
        return ""

def speak_text(text):
    print(f"Assistant says: {text}")
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE # Or MALE, NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3 # Or LINEAR16 for raw audio
    )

    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Play the audio response
    # You might need to save to a temp file and play, or stream directly
    # For simplicity, saving to file and playing:
    with open("response.mp3", "wb") as out:
        out.write(response.audio_content)
    os.system("mpg123 response.mp3") # Ensure mpg123 is installed: sudo apt-get install mpg123

def get_sensor_data(sensor_type=None):
    # Get data from our initialized sensor modules
    data = {}
    if sensor_type == "gps" or sensor_type is None:
        lat, lon = gps_gsm_module.get_location()
        data['gps'] = {'latitude': lat, 'longitude': lon}
    if sensor_type == "fall" or sensor_type is None:
        accel_data = mpu6050_sensor.read_accel_data()
        # Simple fall detection based on acceleration magnitude
        magnitude = (accel_data['x']**2 + accel_data['y']**2 + accel_data['z']**2)**0.5
        fall_detected = magnitude > 2.0  # threshold for fall detection
        data['fall_detection'] = "Detected" if fall_detected else "Not detected"
    if sensor_type == "obstacle" or sensor_type is None:
        distance = ultrasonic_sensor.measure_distance()
        data['obstacle_distance'] = f"{distance:.1f} cm"
    if sensor_type == "object" or sensor_type is None:
        objects = camera_detector.detect_objects()
        data['detected_objects'] = ", ".join(objects) if objects else "None"
    # Add GSM module battery level
    if hasattr(gps_gsm_module, 'get_battery_level'):
        data['battery_level'] = f"{gps_gsm_module.get_battery_level()}%"

    return data

def format_sensor_data_for_speech(data):
    response_parts = []
    if 'gps' in data and data['gps']:
        response_parts.append(f"Your current location is Latitude {data['gps']['latitude']:.4f}, Longitude {data['gps']['longitude']:.4f}.")
    if 'fall_detection' in data:
        response_parts.append(f"Fall detection status: {data['fall_detection']}.")
    if 'obstacle_distance' in data:
        response_parts.append(f"Obstacle detected at approximately {data['obstacle_distance']}.")
    if 'detected_objects' in data:
        response_parts.append(f"I see: {data['detected_objects']}.")
    # Add more sensor data formatting
    # if 'battery_level' in data:
    #     response_parts.append(f"Battery level is {data['battery_level']} percent.")

    if not response_parts:
        return "I don't have information for that, or no sensor data is available."
    return " ".join(response_parts)

def process_command(command_text):
    command_text_lower = command_text.lower()

    if "hello" in command_text_lower or "hi" in command_text_lower:
        speak_text("Hello! How can I assist you today?")
    elif "location" in command_text_lower or "where am i" in command_text_lower:
        speak_text("Fetching your current location...")
        data = get_sensor_data(sensor_type="gps")
        speak_text(format_sensor_data_for_speech(data))
    elif "sensor values" in command_text_lower or "read sensors" in command_text_lower:
        speak_text("Retrieving all available sensor data.")
        data = get_sensor_data() # Get all sensor data
        speak_text(format_sensor_data_for_speech(data))
    elif "obstacle" in command_text_lower or "is there anything ahead" in command_text_lower:
        speak_text("Checking for obstacles.")
        data = get_sensor_data(sensor_type="obstacle")
        speak_text(format_sensor_data_for_speech(data))
    elif "objects" in command_text_lower or "what do you see" in command_text_lower:
        speak_text("Analyzing objects in view.")
        data = get_sensor_data(sensor_type="object")
        speak_text(format_sensor_data_for_speech(data))
    elif "fall status" in command_text_lower or "check fall" in command_text_lower:
        speak_text("Checking fall detection status.")
        data = get_sensor_data(sensor_type="fall")
        speak_text(format_sensor_data_for_speech(data))
    elif "goodbye" in command_text_lower or "bye" in command_text_lower:
        speak_text("Goodbye! Stay safe.")
        return False # Indicate to exit loop
    else:
        speak_text("I'm sorry, I don't understand that command. Please try again.")
    return True # Indicate to continue loop

# --- Main Loop ---
if __name__ == "__main__":
    try:
        speak_text("Hello, I am your walking stick assistant. Press the button to speak.")
        while True:
            # Wait for button press (rising edge)
            GPIO.wait_for_edge(PTT_BUTTON_PIN, GPIO.FALLING) # Button pressed (pulled low)
            print("Button pressed. Starting audio capture.")
            time.sleep(0.1) # Debounce

            audio_data = record_audio()
            transcript = transcribe_audio(audio_data)

            if transcript:
                if not process_command(transcript):
                    break
            else:
                speak_text("I didn't catch that. Could you please repeat?")

            time.sleep(1) # Small delay before checking for next button press

    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        GPIO.cleanup()