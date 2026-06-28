import cv2
import numpy as np
import time
from datetime import datetime

# --- CONFIGURATION SECTION ---
# List of your 4 RTSP URLs
RTSP_URLS = [
    "rtsp://USERNAME:PASSWORD@192.168.x.x:554/Streaming/Channels/2301",
    "rtsp://USERNAME:PASSWORD@192.168.x.x:554/Streaming/Channels/2402",
    "rtsp://USERNAME:PASSWORD@192.168.x.x:554/Streaming/Channels/2501",
    "rtsp://USERNAME:PASSWORD@192.168.x.x:554/Streaming/Channels/2601"
]

CAPTURE_INTERVAL = 10 
LEARNING_FRAMES = 20
ALPHA = 0.1

# Track alerts per camera
current_alerts = ["OK"] * 8

def send_alert(cam_idx, issue, value):
    global current_alerts
    current_alerts[cam_idx] = f"{issue} ({value:.2f})"
    print(f"[{datetime.now()}] CAM {cam_idx} ALERT → {issue} (Value: {value:.2f})")

def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = np.mean(gray)
    noise = np.std(gray)
    return blur, brightness, noise


def draw_overlay(frame, blur, brightness, noise, cam_idx):
    global current_alerts
    # Create a copy so we don't destroy the original frame data
    overlay = frame.copy()
    alert_text = current_alerts[cam_idx]
    
    # Red for alerts, Green for OK
    color = (0, 255, 0) if "OK" in alert_text.upper() else (0, 0, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 1. ADD A BACKGROUND RECTANGLE (Crucial for visibility on a small grid)
    # This adds a semi-transparent black bar at the top for the metrics
    cv2.rectangle(overlay, (0, 0), (120, 55), (0, 0, 0), -1)
    
    # 2. METRICS (Top Left)
    # Scale: 0.4 | Thickness: 1 | Line Spacing: 15px
    cv2.putText(overlay, f"B: {blur:.1f}", (5, 15), font, 0.4, (0, 255, 0), 1)
    cv2.putText(overlay, f"L: {brightness:.1f}", (5, 30), font, 0.4, (0, 255, 0), 1)
    cv2.putText(overlay, f"N: {noise:.1f}", (5, 45), font, 0.4, color, 1)

    # 3. STATUS MESSAGE (Bottom Left)
    # Scale: 0.5 | Thickness: 2 | Positioned near the bottom (y=225)
    # Adding a background strip for the status text too
    cv2.rectangle(overlay, (0, 210), (320, 240), (0, 0, 0), -1)
    cv2.putText(overlay, f"CAM {cam_idx}: {alert_text}", (5, 230), font, 0.5, color, 2)

    # 4. BLEND THE OVERLAY (Professional look)
    # 0.7 Alpha makes the black boxes slightly transparent so you can still see the video behind
    return cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)

# def draw_overlay(frame, blur, brightness, noise, cam_idx):
#     global current_alerts
#     overlay = frame.copy()
#     alert_text = current_alerts[cam_idx]
    
#     color = (0, 255, 0) if "OK" in alert_text.upper() else (0, 0, 255)
    
#     # Positioned slightly higher to fit in grid view
#     cv2.putText(overlay, f"Blur: {blur:.2f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
#     cv2.putText(overlay, f"Bright: {brightness:.2f}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
#     cv2.putText(overlay, f"Noise: {noise:.2f}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
#     cv2.putText(overlay, f"STATUS: {alert_text}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
#     # cv2.putText(overlay, f"CAM {cam_idx}", (550, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
#     return overlay

def monitor_camera():
    # Initialize all 4 captures
    caps = [cv2.VideoCapture(url) for url in RTSP_URLS]
    for i, cap in enumerate(caps):
        if not cap.isOpened():
            print(f"Camera {i} connection failed")
            return

    # Baselines list for each camera , 4 as the number of grid is 4
    blur_means = [0.0]*8; 
    bright_means = [0.0]*8; 
    noise_means = [0.0]*8
    reference_frames = [None]*8

    last_check_time = time.time()

    print("Learning baseline for all cameras...")

    # Simplified learning phase for 4 cams
    for _ in range(LEARNING_FRAMES):
        for i in range(8):
            ret, frame = caps[i].read()
            if ret: #resizing the frames for each grid for the monitor
                frame = cv2.resize(frame, (320, 240)) # 640/480 for 4 camera grid
                #before calculating the mean take the values and assign them to the means list for each camera
                b, br, n = get_metrics(frame)
                blur_means[i] += b
                bright_means[i] += br
                noise_means[i] += n
        cv2.waitKey(1)

    #take the values from the list and put those in temp var x one by one and then divide by the number of learning frames
    blur_means = [x/LEARNING_FRAMES for x in blur_means]
    bright_means = [x/LEARNING_FRAMES for x in bright_means]
    noise_means = [x/LEARNING_FRAMES for x in noise_means]

    while True:
        frames_to_grid = []

        for i in range(8):
            ret, frame = caps[i].read()
            
            # Reset logic per camera
            if not ret:
                caps[i].set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame = np.zeros((240, 320, 3), dtype=np.uint8) #uint8 is a parameter used in NumPy to specify that an array should store 8-bit unsigned integers
                # 3 is the number of color channels(BGR)
            else:
                frame = cv2.resize(frame, (320, 240))

            blur, brightness, noise = get_metrics(frame)

            # Reset status visibility
            if time.time() - last_check_time > 2:
                current_alerts[i] = "OK"

            # --- DIAGNOSTIC CHECK ---
            if time.time() - last_check_time > CAPTURE_INTERVAL:
                # if reference_frames[i] is not None:
                #     diff = cv2.absdiff(reference_frames[i], frame).mean()
                #     if diff < 2.0: send_alert(i, "Frozen", diff)

                if brightness < bright_means[i] * 0.3 and noise > noise_means[i] * 1.5:
                    send_alert(i, "IR Failure", noise)
                elif blur < blur_means[i] * 0.5:
                    send_alert(i, "Blurry", blur)
                elif brightness < bright_means[i] * 0.3:
                    send_alert(i, "Low Light", brightness)
                elif blur == 0 and brightness == 0 and noise == 0:
                    send_alert(i, "Stream Lost")
                
                
                if "OK" in current_alerts[i].upper():
                    blur_means[i] = (1 - ALPHA) * blur_means[i] + ALPHA * blur
                    bright_means[i] = (1 - ALPHA) * bright_means[i] + ALPHA * brightness
                    noise_means[i] = (1 - ALPHA) * noise_means[i] + ALPHA * noise

                reference_frames[i] = frame.copy()

            # Process frame for grid
            processed = draw_overlay(frame, blur, brightness, noise, i)
            frames_to_grid.append(processed)

        # --- GRID ASSEMBLY SECTION ---
        # Stack Top Row (Cam 0, 1) and Bottom Row (Cam 2, 3)
        top_row = np.hstack((frames_to_grid[0], frames_to_grid[1], frames_to_grid[2], frames_to_grid[3]))
        bottom_row = np.hstack((frames_to_grid[4], frames_to_grid[5], frames_to_grid[6], frames_to_grid[7]))
        grid = np.vstack((top_row, bottom_row))
        
        # Resize grid to fit screen if needed (optional)
        grid_display = cv2.resize(grid, (1280, 720)) 
        cv2.imshow("Eight camera grid", grid_display)

        if time.time() - last_check_time > CAPTURE_INTERVAL:
            last_check_time = time.time()

        if cv2.waitKey(1) & 0xFF == 27:
            break

    for cap in caps: cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    monitor_camera()
