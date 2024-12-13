# -*- coding: utf-8 -*-
"""
Created on Thu Sep  5 17:30:29 2024

@author: Abdur Rahim
"""

# -*- coding: utf-8 -*-
"""
Created on Sun Aug 18 00:08:17 2024

@author: Abdur Rahim
"""
from ultralytics import YOLO
import cv2
import math 
from collections import deque
import numpy as np
import time

class YOLOCamera:
    def __init__(self, model_path="C:/models/yolo/yolov8n.pt", camera_index=0, width=640, height=480, target_class="person", confidence_threshold=0.4):
        # Initialize camera
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(3, width)
        self.cap.set(4, height)

        # Initialize model
        self.model = YOLO(model_path)

        # Target object and confidence threshold
        self.target_class = target_class
        self.confidence_threshold = confidence_threshold

        # Object classes
        self.classNames = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
                           "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
                           "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
                           "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
                           "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
                           "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
                           "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
                           "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
                           "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
                           "teddy bear", "hair drier", "toothbrush"]

        # Distance estimation parameters
        self.real_width = 0.5   # meters, adjust this to the actual width of the target object
        self.known_distance = 2.0  # meters, the distance at which the known_width_in_image was measured
        self.known_width_in_image = 200  # pixels, the width of the object in the image at known_distance

        # Calculate the focal length
        self.focal_length = (self.known_width_in_image * self.known_distance) / self.real_width

        # Buffers to store recent distance measurements and bounding box widths
        self.distance_buffer = deque(maxlen=5)
        self.width_buffer = deque(maxlen=5)

    def run_person_detection_step(self, img):
        """
        Runs one step of person detection and returns detection results for processing.
        """
        
        results = self.model(img, stream=True)
        timestamp = time.time()  # Capture current time for sync
        
        person_detected = False  # Flag to indicate if a person was detected
        smoothed_distance = None  # Initialize distance as None
        
        for r in results:
            boxes = r.boxes
            
            for box in boxes:
                confidence = box.conf[0]
                
                if confidence > self.confidence_threshold:
                    cls = int(box.cls[0])
                    class_name = self.classNames[cls]
                    
                    if class_name == self.target_class:
                        person_detected = True
                        x1, y1, x2, y2 = box.xyxy[0]
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)  # Convert to int values
                        
                        # Calculate the width of the bounding box in pixels
                        width_in_image = x2 - x1
                        
                        if width_in_image > 0:
                            # Smooth the bounding box width using a buffer
                            self.width_buffer.append(width_in_image)
                            smoothed_width = np.mean(self.width_buffer)
                            
                            # Estimate the distance to the object
                            distance = (self.real_width * self.focal_length) / smoothed_width
                            
                            # Add the distance to the buffer and calculate smoothed distance
                            self.distance_buffer.append(distance)
                            smoothed_distance = np.mean(self.distance_buffer)
                            
                                    
                            # Draw bounding box and label on the image
                            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
                            cv2.putText(img, f"{class_name} {smoothed_distance:.2f}m", (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 
                                        1, (255, 0, 0), 2)
                            
                            # Update flag to indicate person detected
                            
                # else:
                #     person_detected= False
                            
                            
        # Return detection result after processing all objects in the frame
        return {
            "person_detected": person_detected,
            "distance": smoothed_distance if person_detected else None,
            "image": img,  # Updated image with bounding box and text (if person detected)
            "timestamp": timestamp  # Add timestamp here
            }
           
