from ultralytics import YOLO
import cv2
import time
import threading
from queue import Queue

class ObjectDetector:
    def __init__(self, model_path='yolov8n.pt', conf_thresh=0.25):
        """Initialize object detector with YOLOv8.
        
        Args:
            model_path: Path to YOLOv8 model file
            conf_thresh: Confidence threshold for detections
        """
        # Load YOLOv8 model
        self.model = YOLO(model_path)
        self.model.fuse()  # Fuse layers for optimal performance
        self.conf_thresh = conf_thresh
        
        # Initialize camera and processing components
        self.camera = None
        self.frame_queue = Queue(maxsize=2)  # Raw frame queue
        self.result_queue = Queue(maxsize=2)  # Processed frame queue
        self.running = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
    def find_camera(self):
        """Find and configure USB camera."""
        for index in range(5):
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                print(f"Camera found at index: {index}")
                
                # Optimized camera settings for detection
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)  # Square input for YOLO
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                
                self.camera = cap
                return True
                
            cap.release()
        
        print("No camera found!")
        return False
    
    def _capture_loop(self):
        """Camera capture thread."""
        while self.running:
            if not self.frame_queue.full():
                ret, frame = self.camera.read()
                if ret:
                    # Ensure square input for YOLO
                    frame = cv2.resize(frame, (640, 640))
                    self.frame_queue.put(frame)
    
    def _detection_loop(self):
        """Object detection thread."""
        while self.running:
            if not self.frame_queue.empty() and not self.result_queue.full():
                frame = self.frame_queue.get()
                
                # Run YOLOv8 inference
                results = self.model(frame, conf=self.conf_thresh, verbose=False)[0]
                
                # Calculate FPS
                self.frame_count += 1
                elapsed_time = time.time() - self.start_time
                if elapsed_time > 1:
                    self.fps = self.frame_count / elapsed_time
                    self.frame_count = 0
                    self.start_time = time.time()
                
                # Draw detections and FPS
                annotated_frame = results.plot()
                cv2.putText(annotated_frame, f"FPS: {self.fps:.1f}", 
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                          1, (0, 255, 0), 2)
                
                # Get detection information
                detections = []
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = results.names[cls_id]
                    coords = box.xyxy[0].tolist()  # Get bbox coordinates
                    
                    detection_info = {
                        'class': name,
                        'confidence': conf,
                        'bbox': coords,
                        'center': [(coords[0] + coords[2])/2, (coords[1] + coords[3])/2]
                    }
                    detections.append(detection_info)
                
                # Add detection text to frame
                y_pos = 60
                for det in detections:
                    text = f"{det['class']}: {det['confidence']:.2f}"
                    cv2.putText(annotated_frame, text, 
                              (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                              0.6, (0, 255, 0), 2)
                    y_pos += 30
                
                self.result_queue.put((annotated_frame, detections))
    
    def start(self):
        """Start object detection system."""
        if not self.find_camera():
            return False
            
        self.running = True
        
        # Start capture and detection threads
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.detection_thread = threading.Thread(target=self._detection_loop)
        
        self.capture_thread.daemon = True
        self.detection_thread.daemon = True
        
        self.capture_thread.start()
        self.detection_thread.start()
        return True
    
    def get_detections(self):
        """Get the latest frame and detections."""
        if not self.result_queue.empty():
            return self.result_queue.get()
        return None, None
    
    def stop(self):
        """Stop detection and release resources."""
        self.running = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=1)
        if hasattr(self, 'detection_thread'):
            self.detection_thread.join(timeout=1)
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()

def main():
    """Test object detection system."""
    detector = ObjectDetector()
    
    try:
        if not detector.start():
            return
            
        print("Object Detection Test - Press 'q' to quit")
        print("\nOptimizations active:")
        print("- Threaded capture and detection")
        print("- Minimal frame buffer")
        print("- MJPG format")
        print("- Model fusion")
        print("- Square input resolution")
        
        while True:
            frame, detections = detector.get_detections()
            
            if frame is not None:
                cv2.imshow('YOLOv8 Detection', frame)
                if detections:
                    print("\nDetected Objects:")
                    print("-" * 50)
                    for det in detections:
                        print(f"Object: {det['class']}")
                        print(f"Confidence: {det['confidence']:.2f}")
                        print(f"Position: (x={det['center'][0]:.1f}, y={det['center'][1]:.1f})")
                        print(f"Bounding Box: {[round(x) for x in det['bbox']]}")
                        print("-" * 50)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        detector.stop()

if __name__ == "__main__":
    main()
