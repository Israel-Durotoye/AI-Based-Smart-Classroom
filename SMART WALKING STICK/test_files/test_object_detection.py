# -*- coding: utf-8 -*-

from ultralytics import YOLO
from picamera2 import Picamera2
from libcamera import controls
import cv2
import time
import threading
from queue import Queue
import numpy as np
import pyttsx3
from test_ultrasonic import UltrasonicSensor

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
        
        # Thread control flag and queues
        self.running = False
        self.frame_queue = Queue(maxsize=2)  
        self.result_queue = Queue(maxsize=2)
        
        # Optimization settings
        self.conf_thresh = conf_thresh
        self.input_size = (320, 320)  # Smaller input size for better performance
        self.skip_frames = 2  # Process every Nth frame
        self.frame_counter = 0
        
        # Initialize ultrasonic sensor
        self.ultrasonic = UltrasonicSensor()
        
        # Initialize text-to-speech engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # Speed of speech
        self.engine.setProperty('volume', 0.9)
        self.speech_queue = Queue()
        self.last_speech_time = 0
        self.speech_thread = threading.Thread(target=self._speech_loop)
        self.speech_thread.daemon = True
        self.speech_thread.start()

        # Object-specific prompts
        self.object_prompts = {
            'person': "There is a person",
            'car': "Warning: There is a car",
            'truck': "Caution: There is a truck",
            'bicycle': "There is a bicycle", 
            'motorcycle': "Warning: There is a motorcycle",
            'dog': "There is a dog",
            'chair': "There is a chair",
            'bench': "There is a bench",
            'stairs': "Caution: There are stairs"
        }

        # Initialize detection-related attributes
        self.detected_objects = {}  # Track objects over time
        self.object_history = {}   # Track object positions
        self.last_detections = []  # Store last detection results
        
        # Initialize camera attribute
        self.camera = None
        
        # Distance estimation parameters
        self.focal_length = 1000  # Will be calibrated
        self.known_width = {     # Known width of objects in meters
            'person': 0.5,
            'car': 1.8,
            'chair': 0.5,
            'bench': 1.5
        }
        
        # Performance monitoring
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.processing_times = []
        
    def detect_objects(self, frame):
        """Detect objects in frame with optimizations."""
        try:
            # Skip frames for performance
            self.frame_counter += 1
            if self.frame_counter % self.skip_frames != 0:
                return self.last_detections if hasattr(self, 'last_detections') else []
            
            # Start timing
            start_time = time.time()
            
            # Resize for faster processing
            frame = cv2.resize(frame, self.input_size)
            
            # Run inference
            results = self.model(frame, 
                               conf=self.conf_thresh, 
                               verbose=False,
                               agnostic_nms=True)[0]  # Class-agnostic NMS
            
            # Process detections
            detections = []
            detected_classes = {}
            
            for box in results.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                name = results.names[cls_id]
                coords = box.xyxy[0].tolist()
                
                # Check if object is important and meets threshold
                if name in self.important_objects and conf >= self.important_objects[name]:
                    # Calculate distance if known width available
                    distance = None
                    if name in self.known_width:
                        pixel_width = coords[2] - coords[0]
                        if pixel_width > 0:
                            distance = (self.known_width[name] * self.focal_length) / pixel_width
                    
                    detection_info = {
                        'class': name,
                        'confidence': conf,
                        'bbox': coords,
                        'center': [(coords[0] + coords[2])/2, (coords[1] + coords[3])/2],
                        'distance': distance,
                        'urgent': self._is_urgent(name, distance) if distance else False
                    }
                    detections.append(detection_info)
                    
                    # Update object tracking
                    if name not in detected_classes:
                        detected_classes[name] = 1
                    else:
                        detected_classes[name] += 1
            
            # Update tracking
            self.detected_objects = detected_classes
            self.last_detections = detections
            
            # Update performance metrics
            process_time = time.time() - start_time
            self.processing_times.append(process_time)
            if len(self.processing_times) > 30:
                self.processing_times.pop(0)
            
            self.frame_count += 1
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 1:
                self.fps = self.frame_count / elapsed_time
                self.frame_count = 0
                self.start_time = time.time()
            
            return detections
            
        except Exception as e:
            print(f"Error in object detection: {e}")
            return []
            
    def _is_urgent(self, object_class, distance):
        """Determine if an object needs immediate attention."""
        if distance is None:
            return False
            
        # Distance thresholds in meters
        urgent_distances = {
            'person': 2.0,
            'car': 5.0,
            'truck': 6.0,
            'bicycle': 3.0,
            'motorcycle': 4.0,
            'dog': 2.0,
            'chair': 1.5,
            'bench': 2.0,
            'stairs': 2.0
        }
        
        return object_class in urgent_distances and distance <= urgent_distances[object_class]
        
    def get_performance_stats(self):
        """Get performance statistics."""
        if not self.processing_times:
            return None
            
        return {
            'fps': self.fps,
            'avg_process_time': sum(self.processing_times) / len(self.processing_times),
            'min_process_time': min(self.processing_times),
            'max_process_time': max(self.processing_times)
        }
        
    def calibrate_focal_length(self, known_distance, known_width, measured_width_px):
        """Calibrate focal length using an object of known size at known distance."""
        self.focal_length = (measured_width_px * known_distance) / known_width
        print(f"Calibrated focal length: {self.focal_length:.2f}")
        return self.focal_length

    def init_camera(self):
        """Initialize and configure Raspberry Pi camera."""
        try:
            self.camera = Picamera2()
            
            # Configure camera for optimal object detection
            config = self.camera.create_preview_configuration(
                main={"size": (640, 640), "format": "RGB888"},  # Square input for YOLO
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
    
    def _capture_loop(self):
        """Camera capture thread."""
        while self.running:
            if not self.frame_queue.full():
                # Capture frame using Picamera2
                frame = self.camera.capture_array()
                # No need to resize as we configured the camera for 640x640
                self.frame_queue.put(frame)
    
    def _speech_loop(self):
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

    def speak(self, text, min_interval=3):
        """Add text to speech queue with rate limiting."""
        current_time = time.time()
        if current_time - self.last_speech_time >= min_interval:
            self.speech_queue.put(text)
            self.last_speech_time = current_time

    def _format_distance_message(self, object_name, distance=None):
        """Format message with distance information."""
        if distance is None:
            distance = self.ultrasonic.measure_distance()
        
        base_message = self.object_prompts.get(object_name, f"There is a {object_name}")
        
        if distance is not None:
            if distance < 100:  # Less than 1 meter
                return f"{base_message} very close, approximately {int(distance)} centimeters ahead"
            else:
                meters = distance / 100
                return f"{base_message} approximately {meters:.1f} meters ahead"
        
        return base_message + " nearby"

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
                
                # Process and announce detections
                detections = []
                detected_classes = {}
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = results.names[cls_id]
                    coords = box.xyxy[0].tolist()
                    
                    detection_info = {
                        'class': name,
                        'confidence': conf,
                        'bbox': coords,
                        'center': [(coords[0] + coords[2])/2, (coords[1] + coords[3])/2]
                    }
                    detections.append(detection_info)
                    
                    # Track object classes
                    if name not in detected_classes:
                        detected_classes[name] = 1
                        # Announce new object with distance
                        message = self._format_distance_message(name)
                        self.speak(message)
                    else:
                        detected_classes[name] += 1
                
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
        if not self.init_camera():
            return False
            
        # Start the camera
        self.camera.start()
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
            self.camera.stop()
        if hasattr(self, 'ultrasonic'):
            self.ultrasonic.cleanup()
        cv2.destroyAllWindows()

def main():
    """Test object detection system with speech feedback."""
    detector = ObjectDetector()
    
    try:
        if not detector.start():
            return
            
        print("Object Detection Test - Press 'q' to quit")
        print("\nOptimizations and features active:")
        print("- Threaded capture and detection")
        print("- Hardware-accelerated camera capture")
        print("- Native RGB format")
        print("- Model fusion")
        print("- Square input resolution")
        print("- Minimal noise reduction")
        print("- Real-time distance measurements")
        print("- Voice announcements for detected objects")
        
        # Initial announcement
        detector.speak("Object detection system initialized. I will announce objects I detect and their approximate distance.")
        
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
