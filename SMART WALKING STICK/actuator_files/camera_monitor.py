# -*- coding: utf-8 -*-

from picamera2 import Picamera2
from libcamera import controls
import cv2
import numpy as np
import time
import threading
from test_object_detection import ObjectDetector

class CameraMonitor:
    def __init__(self, resolution=(416, 416), framerate=15):
        """Initialize the camera with optimized settings for real-time object detection.
        Using 416x416 resolution which is optimal for many object detection models.
        Reduced framerate to 15fps for better processing performance."""
        self.picam2 = Picamera2()
        
        # Configure camera for optimal grayscale performance
        config = self.picam2.create_preview_configuration(
            main={"size": resolution, "format": "YUV420"},  # YUV420 for grayscale
            controls={"FrameDurationLimits": (66666, 66666)}  # ~15fps
        )
        self.picam2.configure(config)
        
        # Optimize camera parameters for performance
        self.picam2.set_controls({
            "AwbEnable": False,  # Disable white balance for grayscale
            "AeEnable": True,    # Keep auto exposure
            "FrameRate": framerate,
            "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off,  # Disable noise reduction
            "Sharpness": 0,      # Disable sharpening
            "FrameSkips": 1      # Skip every other frame
        })
        
        # Initialize object detector
        self.detector = ObjectDetector()
        
        # Threading setup
        self.running = False
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.latest_detections = []
        self.detected_objects = {}  # Track detected objects and their counts
        self.last_announcement = 0
        self.min_announcement_interval = 5  # Minimum seconds between announcements
        
    def start(self):
        """Start the camera and detection thread."""
        try:
            self.picam2.start()
            self.running = True
            self.camera_thread = threading.Thread(target=self._camera_loop)
            self.camera_thread.daemon = True
            self.camera_thread.start()
            print("Camera monitoring started successfully")
            return True
        except Exception as e:
            print(f"Error starting camera: {e}")
            return False
            
    def _camera_loop(self):
        """Main camera processing loop optimized for grayscale processing."""
        frame_count = 0
        process_every_n_frames = 3  # Process every 3rd frame
        
        while self.running:
            try:
                # Capture frame in YUV420 format
                frame = self.picam2.capture_array()
                frame_count += 1
                
                # Process only every nth frame
                if frame_count % process_every_n_frames != 0:
                    continue
                
                # Extract Y (grayscale) channel from YUV420
                gray_frame = frame[:frame.shape[0]*2//3].reshape(frame.shape[0], -1)
                
                # Ensure frame size is correct for the model (416x416)
                if gray_frame.shape != (416, 416):
                    gray_frame = cv2.resize(gray_frame, (416, 416))
                
                # Normalize pixel values
                gray_frame = gray_frame.astype(np.float32) / 255.0
                
                # Run object detection on grayscale frame
                detections = self.detector.detect_objects(gray_frame)
                
                # Update latest frame and detections
                with self.frame_lock:
                    self.latest_frame = gray_frame
                    self.latest_detections = detections
                    
                    # Update object tracking with confidence threshold
                    current_objects = {}
                    for det in detections:
                        if det['confidence'] > 0.4:  # Increased confidence threshold
                            obj_class = det['class']
                            current_objects[obj_class] = current_objects.get(obj_class, 0) + 1
                    
                    self.detected_objects = current_objects
                
            except Exception as e:
                print(f"Error in camera loop: {e}")
                time.sleep(1)
                
    def get_latest_frame(self):
        """Get the latest processed frame with detections drawn."""
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            
            # Convert grayscale to 3-channel for visualization
            frame = cv2.cvtColor(self.latest_frame, cv2.COLOR_GRAY2BGR)
            frame = (frame * 255).astype(np.uint8)  # Denormalize
            
            # Draw detections (only high confidence)
            for det in self.latest_detections:
                if det['confidence'] > 0.4:  # Only draw high confidence detections
                    bbox = det['bbox']
                    label = f"{det['class']}: {det['confidence']:.2f}"
                cv2.rectangle(frame, 
                            (int(bbox[0]), int(bbox[1])), 
                            (int(bbox[2]), int(bbox[3])), 
                            (0, 255, 0), 2)
                            
                # Draw label
                cv2.putText(frame, label,
                          (int(bbox[0]), int(bbox[1] - 10)),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                          (0, 255, 0), 2)
                          
            return frame
            
    def get_object_summary(self):
        """Get a summary of detected objects for speech announcements."""
        with self.frame_lock:
            current_time = time.time()
            if not self.detected_objects or \
               (current_time - self.last_announcement) < self.min_announcement_interval:
                return None
                
            # Create summary message
            messages = []
            for obj_class, count in self.detected_objects.items():
                if count > 0:
                    messages.append(f"{count} {obj_class}{'s' if count > 1 else ''}")
                    
            if messages:
                self.last_announcement = current_time
                return "I can see " + ", and ".join(messages)
            return None
            
    def stop(self):
        """Stop the camera and cleanup."""
        self.running = False
        if hasattr(self, 'camera_thread'):
            self.camera_thread.join(timeout=1)
        if hasattr(self, 'picam2'):
            self.picam2.stop()
            print("Camera stopped and cleaned up")
