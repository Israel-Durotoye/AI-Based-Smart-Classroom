import cv2
import time
import threading
from queue import Queue

class USBCamera:
    def __init__(self):
        """Initialize USB camera with optimized settings."""
        self.camera = None
        self.frame_queue = Queue(maxsize=2)  # Small queue to reduce latency
        self.running = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
    def find_camera(self):
        """Find and configure USB camera."""
        # Try camera indices 0 through 4
        for index in range(5):
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                print(f"Camera found at index: {index}")
                
                # Set optimized camera properties
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer size
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                
                self.camera = cap
                return True
                
            cap.release()
        
        print("No camera found!")
        return False
    
    def start_capture(self):
        """Start camera capture thread."""
        if not self.find_camera():
            return False
            
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        return True
    
    def _capture_loop(self):
        """Camera capture loop running in separate thread."""
        while self.running:
            if not self.frame_queue.full():
                ret, frame = self.camera.read()
                if ret:
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
            self.camera.release()
        cv2.destroyAllWindows()

def main():
    """Test USB camera with optimized settings."""
    camera = USBCamera()
    
    try:
        if not camera.start_capture():
            return
            
        print("Camera Test - Press 'q' to quit")
        print("\nOptimizations active:")
        print("- Threaded capture")
        print("- Minimal frame buffer")
        print("- MJPG format")
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
