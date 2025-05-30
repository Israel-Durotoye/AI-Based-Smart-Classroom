from picamera2 import Picamera2
from libcamera import controls
import cv2
import time
import threading
from queue import Queue

class PiCamera:
    def __init__(self):
        """Initialize Raspberry Pi camera with optimized settings."""
        self.camera = None
        self.frame_queue = Queue(maxsize=2)  # Small queue to reduce latency
        self.running = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
    def init_camera(self):
        """Initialize and configure the Raspberry Pi camera."""
        try:
            self.camera = Picamera2()
            
            # Configure camera for optimal performance
            config = self.camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                controls={"FrameDurationLimits": (33333, 33333)}  # ~30fps
            )
            self.camera.configure(config)
            
            # Set camera parameters for better performance
            self.camera.set_controls({
                "AwbEnable": True,  # Auto white balance
                "AeEnable": True,   # Auto exposure
                "FrameRate": 30,
                "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Minimal
            })
            
            print("Camera initialized successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing camera: {e}")
            return False
    
    def start_capture(self):
        """Start camera capture thread."""
        if not self.init_camera():
            return False
            
        # Start the camera
        self.camera.start()
        
        # Start capture thread
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        return True
    
    def _capture_loop(self):
        """Camera capture loop running in separate thread."""
        while self.running:
            if not self.frame_queue.full():
                # Capture frame from Picamera2
                frame = self.camera.capture_array()
                
                # Calculate FPS
                self.frame_count += 1
                elapsed_time = time.time() - self.start_time
                if elapsed_time > 1:
                    self.fps = self.frame_count / elapsed_time
                    self.frame_count = 0
                    self.start_time = time.time()
                
                # Add FPS text to frame
                cv2.putText(frame, f"FPS: {self.fps:.1f}", 
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                          1, (0, 255, 0), 2)
                
                # Put frame in queue
                self.frame_queue.put(frame)
    
    def get_frame(self):
        """Get the latest frame from queue."""
        if not self.frame_queue.empty():
            return self.frame_queue.get()
        return None
    
    def stop(self):
        """Stop camera capture and release resources."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1)
        if self.camera:
            self.camera.stop()
        cv2.destroyAllWindows()

def main():
    """Test Raspberry Pi camera with optimized settings."""
    camera = PiCamera()
    
    try:
        if not camera.start_capture():
            return
            
        print("Camera Test - Press 'q' to quit")
        print("\nOptimizations active:")
        print("- Hardware-accelerated capture")
        print("- Minimal frame buffer")
        print("- Native RGB format")
        print("- Queue size: 2 frames")
        
        while True:
            frame = camera.get_frame()
            if frame is not None:
                cv2.imshow('USB Camera Test', frame)
                
            # Break on 'q' press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        camera.stop()

if __name__ == "__main__":
    main()
