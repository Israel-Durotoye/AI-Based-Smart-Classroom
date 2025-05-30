import cv2
from ultralytics import YOLO
import time
import threading
from queue import Queue
from a9g_module import A9GModule
import os

def is_raspberry_pi():
    return os.path.exists('/proc/cpuinfo') and 'Raspberry Pi' in open('/proc/cpuinfo').read()

def find_camera():
    """Try different camera indices to find the working camera."""
    # Try indices 0 through 4
    for index in range(5):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print(f"Camera found at index: {index}")
            return cap
        cap.release()
    return None

class VideoStreamWidget:
    def __init__(self, model):
        self.model = model
        self.capture = find_camera()
        if self.capture is None:
            raise ValueError("No camera found!")
            
        # Set lower resolution for faster processing
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 416)  # reduced from 640
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 416)  # reduced from 480
        
        # Set buffer size to 1 to reduce latency
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.frame_queue = Queue(maxsize=2)  # Limit queue size
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.latest_detections = []
        
        # Start frame capture thread
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while True:
            if not self.frame_queue.full():
                ret, frame = self.capture.read()
                if ret:
                    # Calculate FPS
                    self.frame_count += 1
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time > 1:
                        self.fps = self.frame_count / elapsed_time
                        self.frame_count = 0
                        self.start_time = time.time()
                    
                    # Resize frame for faster processing
                    frame = cv2.resize(frame, (416, 416))
                    self.frame_queue.put(frame)

    def process_frame(self):
        if not self.frame_queue.empty():
            frame = self.frame_queue.get()
            
            # Run YOLOv8 inference with optimized settings
            results = self.model(frame, conf=0.25, iou=0.45)  # Adjusted confidence and IOU thresholds
            
            # Store detections
            self.latest_detections = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = r.names[cls]
                    self.latest_detections.append(f"{name}: {conf:.2f}")
            
            # Only create annotated frame if we're not on Raspberry Pi
            if not is_raspberry_pi():
                annotated_frame = results[0].plot()
                # Add FPS counter to frame
                cv2.putText(annotated_frame, f"FPS: {self.fps:.1f}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                return annotated_frame
            else:
                # Print detections to console
                if self.latest_detections:
                    print("\nDetections:", self.latest_detections)
                return None
        return None

def main():
    # Load the YOLOv8 model with optimization
    model = YOLO('yolov8n.pt')
    model.fuse()  # Fuse model layers for faster inference
    
    try:
        # Initialize A9G module
        a9g = A9GModule()
        print("Initializing A9G module...")
        a9g.init_module()
        print("A9G module initialized successfully")
        
        # Initialize the video stream
        video_stream = VideoStreamWidget(model)
        print("Camera initialized successfully")
        print("Press Ctrl+C to quit")
        
        running = True
        while running:
            try:
                # Process frame
                frame = video_stream.process_frame()
                
                # Only show frame if not on Raspberry Pi
                if not is_raspberry_pi() and frame is not None:
                    cv2.imshow('YOLOv8 Object Detection', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        running = False
                
                time.sleep(0.1)  # Prevent high CPU usage
                
            except KeyboardInterrupt:
                print("\nStopping...")
                running = False
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if not is_raspberry_pi():
            cv2.destroyAllWindows()
        if 'video_stream' in locals():
            video_stream.capture.release()
        if 'a9g' in locals():
            a9g.cleanup()

if __name__ == '__main__':
    main()
