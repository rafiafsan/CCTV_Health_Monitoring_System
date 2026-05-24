import cv2
import numpy as np
import time
from datetime import datetime

# URL configuration
RTSP_URL = "rtsp://admin:brtl@98987@192.168.186.10:554/Streaming/Channels/3702"

# Configuration
CAPTURE_INTERVAL = 10  
LEARNING_FRAMES = 50
ALPHA = 0.1

# Global status
current_alert = "OK"
last_check_time = time.time()

def send_alert(issue, value=0.0):
    global current_alert, last_check_time
    current_alert = f"{issue} ({value:.2f})"
    last_check_time = time.time() # Reset timer so the alert stays visible
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ALERT → {issue}")

def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = np.mean(gray)
    noise = np.std(gray)
    return blur, brightness, noise

def draw_overlay(frame, blur, brightness, noise):
    global current_alert
    overlay = frame.copy()
    
    # Status color logic
    color = (0, 255, 0) if "OK" in current_alert.upper() else (0, 0, 255)
    
    # Text background for readability
    cv2.rectangle(overlay, (5, 370), (250, 475), (0, 0, 0), -1)
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(overlay, f"Blur: {blur:.1f}", (10, 390), font, 0.5, (0,255,0), 1)
    cv2.putText(overlay, f"Bright: {brightness:.1f}", (10, 410), font, 0.5, (0,255,0), 1)
    cv2.putText(overlay, f"Noise: {noise:.1f}", (10, 430), font, 0.5, (0,255,0), 1)
    cv2.putText(overlay, f"STATUS: {current_alert}", (10, 460), font, 0.6, color, 2)
    
    # Add a translucent effect
    return cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

def monitor_camera():
    global current_alert, last_check_time
    cap = cv2.VideoCapture(RTSP_URL)
    
    if not cap.isOpened():
        print("Error: Could not open video source.")
        return

    # --- 1. BASELINE LEARNING PHASE ---
    blur_list, bright_list, noise_list = [], [], []
    print("Learning baseline... Keep camera steady.")
    
    while len(blur_list) < LEARNING_FRAMES:
        ret, frame = cap.read()
        if not ret: 
            print("Waiting for stream...")
            continue

        frame = cv2.resize(frame, (640, 480))
        b, br, n = get_metrics(frame)
        blur_list.append(b); bright_list.append(br); noise_list.append(n)
        
        cv2.putText(frame, f"Learning: {len(blur_list)}/{LEARNING_FRAMES}", (200, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Camera Monitor", frame)
        cv2.waitKey(1)

    blur_mean = np.mean(blur_list)
    bright_mean = np.mean(bright_list)
    noise_mean = np.mean(noise_list)
    reference_frame = None 

    # --- 2. MAIN MONITORING LOOP ---
    print("Monitoring started.")
    while True:
        ret, frame = cap.read()
        
        if not ret:
            # Handle stream disconnection
            current_alert = "STREAM LOST"
            black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(black_frame, "RECONNECTING...", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
            cv2.imshow("Camera Monitor", black_frame)
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        frame = cv2.resize(frame, (640, 480))
        blur, brightness, noise = get_metrics(frame)

        # Clear alert if more than 3 seconds have passed since the last issue
        if time.time() - last_check_time > 3:
            current_alert = "OK"

        # --- DIAGNOSTIC LOGIC ---
        # Run diagnostics every CAPTURE_INTERVAL seconds
        if time.time() - last_check_time > CAPTURE_INTERVAL:
            
            # Check for Frozen Frame
            if reference_frame is not None:
                diff = cv2.absdiff(cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY), 
                                   cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)).mean()
                if diff < 1.0: # Digital noise is usually > 1.0; < 1.0 is almost certainly frozen
                    send_alert("Frozen", diff)

            # Check for IR / Light / Blur
            if brightness < bright_mean * 0.3 and noise > noise_mean * 1.5:
                send_alert("IR Failure", noise)
            elif blur < blur_mean * 0.4: # Adjusted to 40% for better tolerance
                send_alert("Blurry", blur)
            elif brightness < bright_mean * 0.2: # Adjusted to 20% for deep darkness
                send_alert("Low Light", brightness)
            
            # Update Baselines (Adaptation)
            if "OK" in current_alert.upper():
                blur_mean = (1 - ALPHA) * blur_mean + ALPHA * blur
                bright_mean = (1 - ALPHA) * bright_mean + ALPHA * brightness
                noise_mean = (1 - ALPHA) * noise_mean + ALPHA * noise

            reference_frame = frame.copy()
            last_check_time = time.time()

        # Display output
        display_frame = draw_overlay(frame, blur, brightness, noise)
        cv2.imshow("Camera Monitor", display_frame)

        if cv2.waitKey(1) & 0xFF == 27: # Press ESC to exit
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    monitor_camera()