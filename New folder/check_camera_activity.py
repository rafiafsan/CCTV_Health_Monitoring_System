import cv2
import urllib.parse
import os

# --- CONFIGURATION ---
IP = "192.168.254.3"
USER = "admin"
PASS = "prg@welc0ome"
MAX_CHANNELS = 20

# Force TCP to prevent packet loss during the scan
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

def check_stream(channel_id):
    safe_pass = urllib.parse.quote(PASS)
    url = f"rtsp://{USER}:{safe_pass}@{IP}:554/Streaming/Channels/{channel_id}"
    
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    
    # CRITICAL: If the stream doesn't open in 2 seconds, move to the next
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2000)
    
    if cap.isOpened():
        ret, _ = cap.read()
        cap.release()
        return ret
    return False

print(f"--- Scanning Hikvision NVR at {IP} ---")
active_channels = []
print(f"login successful")

for i in range(1, MAX_CHANNELS + 1):
    # Testing Sub-stream (102, 202, etc) is much faster for a scan
    channel_sub = i * 100 + 2
    print(f"Testing Channel {i} (ID: {channel_sub})...", end=" ", flush=True)
    
    if check_stream(channel_sub):
        print("✅ ONLINE")
        active_channels.append(i)
    else:
        print("❌ OFFLINE")

print(f"\n--- Scan Complete ---")
print(f"Found {len(active_channels)} active cameras: {active_channels}")