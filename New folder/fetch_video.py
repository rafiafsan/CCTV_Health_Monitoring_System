import cv2
import os
import urllib.parse

# 1. Force TCP transport to avoid packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# 2. Properly encoded URL (replacing @ with %40 in the password)
USER = "USER"
PASS = "PASSWORD" # Encoded @
IP = "192.168.x.x"
PORT = "554"
CHANNEL = "102" # 102 is usually the sub-stream (easier to load)

safe_pass = urllib.parse.quote(PASS)

SOURCE = f"rtsp://{USER}:{safe_pass}@{IP}:{PORT}/Streaming/Channels/{CHANNEL}"

print(f"Connecting to: {SOURCE}")

# 3. Use CAP_FFMPEG explicitly
cap = cv2.VideoCapture(SOURCE, cv2.CAP_FFMPEG)

# Set a short timeout so it doesn't hang forever
cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

if not cap.isOpened():
    print("ERROR: Still cannot open the stream.")
else:
    print("SUCCESS: Stream is open!")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Stream stalled...")
            break
            
        cv2.imshow('Diagnostic Stream', frame)
        if cv2.waitKey(1) == 27: # ESC to quit
            break

cap.release()
cv2.destroyAllWindows()
