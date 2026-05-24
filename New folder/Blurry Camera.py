import cv2
import numpy as np
import time
from datetime import datetime


RTSP_URL = "rtsp://admin:brtl@98987@192.168.186.10:554/Streaming/Channels/2301"
# RTSP_URL = "D:\\dataset\\Blurry\\VID_20260126_211625.mp4"

CAPTURE_INTERVAL = 120
LEARNING_FRAMES = 20
ALPHA = 0.1


current_alert = "OK"

def send_alert(issue, value):
    global current_alert
    current_alert = f"{issue} ({value:.2f})"
    print(f"[{datetime.now()}] ALERT → {issue} (Value: {value:.2f})")

def get_blur(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def get_brightness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)

def get_noise(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.std(gray)

def frame_diff(prev, curr):
    return cv2.absdiff(prev, curr).mean()

def draw_overlay(frame, blur, brightness, noise):
    global current_alert

    overlay = frame.copy()

    # Text info
    cv2.putText(overlay, f"Blur: {blur:.2f}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    cv2.putText(overlay, f"Brightness: {brightness:.2f}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    cv2.putText(overlay, f"Noise: {noise:.2f}", (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    # Alert text (big + colored)
    color = (0,255,0) if current_alert == "OK" else (0,0,255)

    cv2.putText(overlay, f"STATUS: {current_alert}", (10, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    return overlay


def monitor_camera():
    cap = cv2.VideoCapture(RTSP_URL)

    if not cap.isOpened():
        print("Camera connection failed")
        return

    print("Camera connected")

    blur_list, bright_list, noise_list = [], [], []  #list of the needed parameters to learn the baseline
    prev_frame = None
    print("Learning baseline...")


    while len(blur_list) < LEARNING_FRAMES:
        ret, frame = cap.read()
        if not ret:   #stop the rest of the code if there's no returned frame
            continue
         
        frame = cv2.resize(frame, (640, 480))  #standarize the frame size to vga for faster processig

        blur_list.append(get_blur(frame))
        bright_list.append(get_brightness(frame))
        noise_list.append(get_noise(frame))

        cv2.putText(frame, f"Learning {len(blur_list)}/{LEARNING_FRAMES}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)

        cv2.imshow("Camera Monitor", frame)

        if cv2.waitKey(1) & 0xFF == 27:  #27 is the ascii code for ESC key,and the code is wait 1 ms for OS to process events
            break

    blur_mean = np.mean(blur_list)
    bright_mean = np.mean(bright_list)
    noise_mean = np.mean(noise_list)

    print(f"Blur:{blur_mean:0.2f} \n Brightness: {bright_mean:0.2f} \n Noise: {noise_mean:0.2f}")
    print("Baseline ready")

    last_check_time = time.time()

    while True:
        ret, frame = cap.read()
        current_alert ="ok"

        if not ret:
            send_alert("Stream Lost", 0) #if not return then skip the rest of the code restart the code again
            continue

        frame = cv2.resize(frame, (640, 480))

        blur = get_blur(frame)
        brightness = get_brightness(frame)
        noise = get_noise(frame)

        print(f"Blur: {blur: 0.2f} \n Brightness: {brightness: 0.2f} \n noise: {noise: 0.2f}")

        if time.time() - last_check_time > CAPTURE_INTERVAL:

            current_alert = "OK"

            # Blur
            if blur < blur_mean * 0.5:
                send_alert("Blurry", blur)

            # Low light
            if brightness < bright_mean * 0.4:
                send_alert("Low Light", brightness)

            # IR failure
            if brightness < bright_mean * 0.4 and noise > noise_mean * 1.5:
                send_alert("IR Failure", noise)

            # Freeze
            if prev_frame is not None:
                diff = frame_diff(prev_frame, frame)
                if diff < 110:
                    send_alert("Frozen", diff)

            # Update baseline (only if OK)  
            # applied EMA to change the baseline aand the ALPHA value set to 0.1 so that the baseline change slowly
            # 0.1 slowchange, 0.01 sets for takes few hours and 0.5 means very highly responsie like 50% of the frames are new
            if current_alert == "OK":
                blur_mean = (1 - ALPHA) * blur_mean + ALPHA * blur
                bright_mean = (1 - ALPHA) * bright_mean + ALPHA * brightness
                noise_mean = (1 - ALPHA) * noise_mean + ALPHA * noise

            last_check_time = time.time()

            # Use delay for manual testing
            # if cv2.waitKey(30) & 0xFF == 27: # 30ms delay approximates 30fps 
            #  break

        prev_frame = frame.copy() #copying recent frame to compare wiht the present frame

        display_frame = draw_overlay(frame, blur, brightness, noise)

        cv2.imshow("Camera Monitor", display_frame)

        # Press ESC to exit
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    monitor_camera()