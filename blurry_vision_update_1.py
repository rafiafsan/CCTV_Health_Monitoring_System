import cv2
import numpy as np
import time
import math
from datetime import datetime
import os
import threading

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"

# --- CONFIGURATION ---
USER = "admin"
PASS = "brtl@98987"
IP_BASE = "192.168.186.10"
# Add your camera numbers here (e.g., 37, 23, 18, 16...)
CAM_NUMBERS = [36, 23, 18, 16, 14, 24, 32, 44, 37, 22, 17, 15, 13, 25, 33, 45] 

CAPTURE_INTERVAL = 5
LEARNING_FRAMES = 50
ALPHA = 0.1
WINDOW_SIZE = 12
THRESHOLD_COUNT = 12
CELL_W, CELL_H = 320, 240 # Size of each individual camera in the grid
    

#this function captures the latest frame from the camera stream in a seperate thread.
class CameraStream:
    def __init__(self, cam_no):
        # 1. Setup the connection details
        self.cam_no = cam_no

        # self.url= get_rtsp_url(cam_no)
        #FOR HIKVISION CAMERAS
        self.url = f"rtsp://{USER}:{PASS}@{IP_BASE}:554/Streaming/Channels/{cam_no}02" 
        
        # 2. Initialize state variables
        self.cap = cv2.VideoCapture(self.url)
        self.ret = False     # Did the latest read succeed?
        self.frame = None    # The actual image data
        self.stopped = False # Kill switch for the thread
        
        # 3. Start the background worker thread(tell itselt to run the update function)
        # daemon=True ensures the thread dies when the main program closes
        threading.Thread(target=self.update, args=(), daemon=True).start()

    def update(self):
        #The loop that runs in the background to grab frames.
        while not self.stopped:
            # If the camera isn't opened, try to connect/reconnect
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.url)
                time.sleep(1) # Wait before retrying to avoid network spam
                continue
            
            # Non-blocking grab of the next frame from the camera buffer
            ret, frame = self.cap.read()
            
            if ret:
                # Resize immediately inside the thread to offload the main CPU
                # CELL_W and CELL_H must be defined globally or passed in
                self.frame = cv2.resize(frame, (320, 240)) 
                self.ret = True
            else:
                # If reading fails, release the resource so the 'isOpened' 
                # check above can try a clean reconnection on the next loop.
                self.ret = False
                self.cap.release()
                time.sleep(0.5)

    def read(self):
        """Used by the main loop to get the most recent frame instantly."""
        return self.ret, self.frame

    def stop(self):
        """Safely shuts down the camera and the thread."""
        self.stopped = True
        if self.cap:
            self.cap.release()
    

def get_rtsp_url(cam_no):
    #Generates URL based on: rtsp://user:pass@IP:554/Streaming/Channels/XX02
    return f"rtsp://{USER}:{PASS}@{IP_BASE}:554/Streaming/Channels/{cam_no}02"

def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = np.mean(gray)
    noise = np.std(gray)
    return blur, brightness, noise

def draw_overlay(frame, blur, brightness, noise, cam_idx, status):
    overlay = frame.copy()
    color = (0, 255, 0) if "OK" in status.upper() else (0, 0, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Metrics Background
    cv2.rectangle(overlay, (0, 0), (100, 50), (0, 0, 0), -1)
    cv2.putText(overlay, f"B: {blur:.1f}", (5, 12), font, 0.35, (0, 255, 0), 1)
    cv2.putText(overlay, f"L: {brightness:.1f}", (5, 25), font, 0.35, (0, 255, 0), 1)
    cv2.putText(overlay, f"N: {noise:.1f}", (5, 38), font, 0.35, color, 1)

    # Status Bar
    cv2.rectangle(overlay, (0, CELL_H-25), (CELL_W, CELL_H), (0, 0, 0), -1)
    cv2.putText(overlay, f"CAM {CAM_NUMBERS[cam_idx]}: {status}", (5, CELL_H-8), font, 0.4, color, 1)

    return cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)

def monitor_camera():
    num_cams = len(CAM_NUMBERS)
    # Calculate Grid Dimensions
    cols = math.ceil(math.sqrt(num_cams))
    rows = math.ceil(num_cams / cols)
    
    print(f"Initializing {num_cams} cameras in a {rows}x{cols} grid...")
    

    #counting the numberof streams 
    # caps = [cv2.VideoCapture(get_rtsp_url(n)) for n in CAM_NUMBERS]
    streams = [CameraStream(n) for n in CAM_NUMBERS]

    blur_flags = [[] for _ in range(num_cams)]
    dark_flags = [[] for _ in range(num_cams)]
    ir_flags = [[] for _ in range(num_cams)]
    
    # Dynamic State Tracking
    blur_means = [0.0] * num_cams
    bright_means = [0.0] * num_cams
    noise_means = [0.0] * num_cams
    current_alerts = ["OK"] * num_cams
    last_check_time = time.time()

    print("Connecting to cameras..")
    time.sleep(2)

    # --- LEARNING PHASE ---
    for _ in range(LEARNING_FRAMES):
        for i in range(num_cams):
            ret, frame = streams[i].read()
            if ret:
                frame = cv2.resize(frame, (CELL_W, CELL_H))
                b, br, n = get_metrics(frame)
                blur_means[i] += b
                bright_means[i] += br
                noise_means[i] += n
        cv2.waitKey(1)

    blur_means = [x/LEARNING_FRAMES for x in blur_means]
    bright_means = [x/LEARNING_FRAMES for x in bright_means]
    noise_means = [x/LEARNING_FRAMES for x in noise_means]

    # --- MAIN LOOP ---
    while True:
        processed_frames = []
        
        for i in range(num_cams):
            ret, frame = streams[i].read()
            # if not ret:
            if not ret or frame is None:
                frame = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
                cv2.putText(frame, "LOST SIGNAL : Reconecting..", (60, CELL_H//2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                blur, brightness, noise = 0, 0, 0
            else:
                frame = cv2.resize(frame, (CELL_W, CELL_H))
                blur, brightness, noise = get_metrics(frame)

            # Logic Check
            if time.time() - last_check_time > CAPTURE_INTERVAL:
                is_blurry = blur < blur_means[i] * 0.5
                is_dark = brightness < bright_means[i] * 0.3
                is_ir_fail = is_dark and noise > noise_means[i] * 1.5

                #apend true and false values to the flags list for each camera
                blur_flags[i].append(is_blurry)
                dark_flags[i].append(is_dark)
                ir_flags[i].append(is_ir_fail)

                if len(blur_flags[i]) > WINDOW_SIZE:
                   blur_flags[i].pop(0)
                   dark_flags[i].pop(0)
                   ir_flags[i].pop(0)

                blur_count = sum(blur_flags[i])
                dark_count = sum(dark_flags[i])
                ir_count = sum(ir_flags[i])
                
                if ir_count >= THRESHOLD_COUNT:
                   current_alerts[i] = "IR Fail"
                elif blur_count >= THRESHOLD_COUNT:
                   current_alerts[i] = "Blurry"
                elif dark_count >= THRESHOLD_COUNT:
                   current_alerts[i] = "Dark"
                else:
                   current_alerts[i] = "OK"
                   blur_means[i] = (1 - ALPHA) * blur_means[i] + ALPHA * blur   
                   bright_means[i] = (1 - ALPHA) * bright_means[i] + ALPHA * brightness
                   noise_means[i] = (1 - ALPHA) * noise_means[i] + ALPHA * noise

                
                # if brightness < bright_means[i] * 0.3 and noise > noise_means[i] * 1.5:
                #     current_alerts[i] = "IR Fail"
                # elif blur < blur_means[i] * 0.5:
                #     current_alerts[i] = "Blurry"
                # elif brightness < bright_means[i] * 0.3:
                #     current_alerts[i] = "Dark"
                # else:
                #     current_alerts[i] = "OK"

                #     # Adaptive EMA
            processed_frames.append(draw_overlay(frame, blur, brightness, noise, i, current_alerts[i]))

        # Clear alert timer
        if time.time() - last_check_time > CAPTURE_INTERVAL:
            last_check_time = time.time()

        # --- DYNAMIC GRID ASSEMBLY ---
        # Add black placeholders if we have empty slots in the grid
        while len(processed_frames) < (rows * cols):
            processed_frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

        grid_rows = []
        for r in range(rows):
            # Slice the list for this row and stack horizontally
            row_data = processed_frames[r*cols : (r+1)*cols]
            grid_rows.append(np.hstack(row_data))
        
        # Stack all rows vertically
        final_grid = np.vstack(grid_rows)
        
        # Final Resize for Monitor (e.g., Fit to 1080p width if grid is huge)
        display_w = min(1920, cols * CELL_W)
        display_h = int(display_w * (final_grid.shape[0] / final_grid.shape[1]))
        
        cv2.imshow("Dynamic Camera Monitor", cv2.resize(final_grid, (display_w, display_h)))

        if cv2.waitKey(1) & 0xFF == 27: break

    for stream in streams: stream.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    monitor_camera()