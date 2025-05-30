#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time

def test_a9g_connection(port='/dev/serial0', baud_rate=115200):
    """
    Test A9G module connection and initialization with comprehensive diagnostics.
    """
    print("\nTesting A9G module connection...")
    
    try:
        # Open serial port with hardware flow control
        ser = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2,
            xonxoff=False,
            rtscts=True,    # Enable hardware flow control
            dsrdtr=True     # Enable hardware flow control
        )
        
        if not ser.is_open:
            ser.open()
        
        print(f"Serial port {port} opened successfully")
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test commands with proper delays
        test_commands = [
            ("AT", 1),             # Basic AT test
            ("AT+CGMM", 1),        # Module model
            ("AT+CPIN?", 1),       # SIM status
            ("AT+CSQ", 1),         # Signal quality
            ("AT+CREG?", 2),       # Network registration
            ("AT+CGPS=1", 2),      # Enable GPS
            ("AT+CGPSINFO", 2),    # GPS information
        ]
        
        results = {}
        for cmd, wait_time in test_commands:
            print(f"\nTesting command: {cmd}")
            
            # Send command with CR+LF
            ser.write(f"{cmd}\r\n".encode())
            time.sleep(wait_time)
            
            # Read response with timeout
            response = bytearray()
            start_time = time.time()
            
            while (time.time() - start_time) < wait_time:
                if ser.in_waiting:
                    new_data = ser.read(ser.in_waiting)
                    response.extend(new_data)
                    if b'OK' in response or b'ERROR' in response:
                        break
                time.sleep(0.1)
            
            try:
                resp_str = response.decode('utf-8', errors='ignore').strip()
                print(f"Response: {resp_str}")
                results[cmd] = resp_str
            except Exception as e:
                print(f"Error decoding response: {e}")
                print(f"Raw response (hex): {response.hex()}")
                results[cmd] = response.hex()
            
            time.sleep(0.5)  # Additional delay between commands
        
        # Analyze results
        print("\nDiagnostic Results:")
        
        # Check basic AT command
        if "OK" in results.get("AT", ""):
            print("✓ Module responds to AT commands")
        else:
            print("✗ Module not responding to AT commands")
            print("  - Check power supply")
            print("  - Verify TX/RX connections")
            print("  - Try power cycling the module")
        
        # Check SIM card status
        sim_response = results.get("AT+CPIN?", "")
        if "READY" in sim_response:
            print("✓ SIM card detected and ready")
        else:
            print("✗ SIM card issue")
            print("  - Check if SIM is inserted properly")
            print("  - Verify SIM card is not locked")
        
        # Check signal strength
        csq_response = results.get("AT+CSQ", "")
        if "+CSQ:" in csq_response:
            try:
                signal = int(csq_response.split(":")[1].strip().split(",")[0])
                print(f"Signal strength: {signal}/31")
                if signal < 10:
                    print("  ⚠ Weak signal - check antenna connection")
            except:
                print("✗ Could not parse signal strength")
        
        # Check network registration
        if "0,1" in results.get("AT+CREG?", "") or "0,5" in results.get("AT+CREG?", ""):
            print("✓ Registered to network")
        else:
            print("✗ Not registered to network")
            print("  - Check antenna connection")
            print("  - Verify SIM card is active")
        
        # Check GPS
        if "+CGPS: 1" in results.get("AT+CGPS=1", ""):
            print("✓ GPS enabled successfully")
        else:
            print("⚠ GPS enable command may have failed")
            print("  - Check GPS antenna connection")
        
        return results
        
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Check if serial port exists:")
        print(f"   ls -l {port}")
        print("2. Check permissions:")
        print("   sudo usermod -a -G dialout $USER")
        print("3. Verify UART is enabled:")
        print("   sudo raspi-config")
        print("   → Interface Options → Serial")
        return None
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
        
    finally:
        try:
            ser.close()
        except:
            pass

if __name__ == "__main__":
    # Try different baud rates
    baud_rates = [115200, 9600, 38400]
    for baud in baud_rates:
        print(f"\nTesting with baud rate: {baud}")
        results = test_a9g_connection(baud_rate=baud)
        if results and "OK" in results.get("AT", ""):
            print(f"\n✓ Success with baud rate {baud}")
            break
        else:
            print(f"✗ Failed with baud rate {baud}")
