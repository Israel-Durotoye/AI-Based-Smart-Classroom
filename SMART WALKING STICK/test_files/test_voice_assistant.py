import sounddevice as sd
import numpy as np
import time
import RPi.GPIO as GPIO
import json

def select_audio_device():
    """Help user select the correct audio device for earpiece/headset"""
    devices = sd.query_devices()
    print("\nAvailable Audio Devices:")
    print("------------------------")
    
    # List all devices
    for i, dev in enumerate(devices):
        channels_in = dev['max_input_channels']
        channels_out = dev['max_output_channels']
        name = dev['name']
        
        if channels_in > 0 and channels_out > 0:
            dev_type = "Input/Output"
        elif channels_in > 0:
            dev_type = "Input"
        else:
            dev_type = "Output"
            
        print(f"{i}: {name} ({dev_type})")
    
    # Help identify headset/earpiece
    print("\nLooking for likely headset/earpiece devices...")
    likely_devices = []
    for i, dev in enumerate(devices):
        name = dev['name'].lower()
        if any(keyword in name for keyword in ['headset', 'headphone', 'earpiece', 'usb audio']):
            if dev['max_input_channels'] > 0 and dev['max_output_channels'] > 0:
                likely_devices.append(i)
                print(f"Possible headset found: Device {i}: {dev['name']}")
    
    return devices, likely_devices

def test_audio_devices():
    """Test audio input and output devices"""
    print("\n=== Audio Device Test ===")
    
    devices, likely_devices = select_audio_device()
    
    # Let user select device
    if likely_devices:
        print("\nFound possible headset device(s)!")
        device_id = likely_devices[0]  # Use first detected headset
        print(f"Using device {device_id}: {devices[device_id]['name']}")
    else:
        print("\nNo obvious headset detected. Please check the device list above.")
        device_id = 0  # Default device
    
    # Set default devices
    sd.default.device = device_id
    
    # Test microphone
    print("\nTesting microphone (recording for 3 seconds)...")
    print("Please speak into your headset/earpiece microphone...")
    duration = 3  # seconds
    fs = 44100    # sample rate
    
    try:
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=device_id)
        sd.wait()
        
        if np.any(recording):
            print("✓ Microphone test successful")
            print(f"   Max input level: {np.max(np.abs(recording)):.2f}")
            if np.max(np.abs(recording)) < 0.1:
                print("   ⚠️ Warning: Input level seems low. Try adjusting microphone volume.")
        else:
            print("❌ Microphone test failed - no audio detected")
            
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
    
    # Test speaker
    print("\nTesting speaker (playing a test tone)...")
    print("You should hear a beep in your earpiece...")
    try:
        # Generate a pleasant beep (440 Hz = A4 note)
        t = np.linspace(0, 0.5, int(fs * 0.5))
        tone = np.sin(2*np.pi*440*t) * 0.5  # 0.5 seconds, half volume
        
        # Add fade in/out to avoid clicks
        fade = 0.1  # seconds
        fade_len = int(fade * fs)
        tone[:fade_len] *= np.linspace(0, 1, fade_len)
        tone[-fade_len:] *= np.linspace(1, 0, fade_len)
        
        sd.play(tone, fs, device=device_id)
        sd.wait()
        print("✓ Speaker test successful")
        
    except Exception as e:
        print(f"❌ Speaker test failed: {e}")
        
    return device_id  # Return selected device ID for use in main assistant

def test_button(pin=18):
    """Test push-to-talk button"""
    print("\n=== Button Test ===")
    print("Testing push-to-talk button on GPIO", pin)
    print("Press the button (5 second test)...")
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    start_time = time.time()
    button_pressed = False
    
    while time.time() - start_time < 5:
        if GPIO.input(pin) == GPIO.LOW:
            button_pressed = True
            print("✓ Button press detected!")
            break
        time.sleep(0.1)
    
    if not button_pressed:
        print("❌ No button press detected")
    
    GPIO.cleanup()
    return button_pressed

def main():
    print("=== Voice Assistant Hardware Test ===")
    
    try:
        # Test audio and get selected device ID
        device_id = test_audio_devices()
        
        # Test button
        button_working = test_button()
        
        # Final status
        print("\n=== Test Results ===")
        if device_id is not None and button_working:
            print("✓ All tests passed! Your hardware is ready.")
            print(f"Selected audio device ID: {device_id}")
            
            # Save device ID for main assistant
            with open('audio_config.json', 'w') as f:
                json.dump({'device_id': device_id}, f)
            print("\nConfiguration saved to audio_config.json")
            
        else:
            print("⚠️ Some tests failed. Please check the errors above.")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
