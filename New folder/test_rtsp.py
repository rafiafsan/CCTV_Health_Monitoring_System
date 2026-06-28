import cv2
import os
import time
import threading

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|timeout;5000000"

url = "rtsp://USER:PASSWORD@192.168.x.x:554/Streaming/Channels/1001"

print("Testing single connection...")
start = time.time()
cap = cv2.VideoCapture(url)
print(f"Connected: {cap.isOpened()}, Time taken: {time.time() - start:.2f}s")
if cap.isOpened():
    ret, frame = cap.read()
    print(f"Frame read: {ret}")
cap.release()

print("\nTesting concurrent connections...")
def connect(i):
    start = time.time()
    cap = cv2.VideoCapture(url)
    print(f"Thread {i} Connected: {cap.isOpened()}, Time taken: {time.time() - start:.2f}s")
    cap.release()

threads = []
for i in range(3):
    t = threading.Thread(target=connect, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
