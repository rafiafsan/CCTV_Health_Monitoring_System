import cv2
import numpy as np
import time
import math
import os
import threading

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"


IP_BASE = "192.168.x.x"
USER = "USER"
PASS = "PASSWORD"
CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10]


CAPTURE_INTERVAL = 3
LEARNING_FRAMES = 50

WINDOW_SIZE = 6
THRESHOLD_COUNT = 6

CELL_W, CELL_H = 320, 240

# ==============================
class CameraStream:
    def __init__(self, cam_no):
        self.url = f"rtsp://{USER}:{PASS}@{IP_BASE}:554/Streaming/Channels/{cam_no}02"
        self.cap = cv2.VideoCapture(self.url)
        self.frame = None
        self.ret = False
        self.lock = threading.Lock()
        self.stopped = False
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while not self.stopped:
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.url)
                time.sleep(1)
                continue

            ret, frame = self.cap.read()

            if ret:
                frame = cv2.resize(frame, (CELL_W, CELL_H))
                with self.lock:
                    self.frame = frame
                    self.ret = True
            else:
                self.ret = False
                self.cap.release()
                time.sleep(0.5)

    def read(self):
        with self.lock:
            return self.ret, self.frame

    def stop(self):
        self.stopped = True
        if self.cap:
            self.cap.release()


# ==============================
def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


    # h, w = gray.shape
    # roi = gray[h//4:3*h//4, w//4:3*w//4]
    roi = gray[:]

    roi = cv2.GaussianBlur(roi, (3, 3), 0)

    gx = cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)
    blur = (gx**2 + gy**2).mean()

    brightness = np.mean(roi)
    noise = np.std(roi)
    contrast = np.std(roi)

    return blur, brightness, noise, contrast

# ==============================
# MAIN
# ==============================
def monitor_camera():

    num_cams = len(CAM_NUMBERS)
    streams = [CameraStream(n) for n in CAM_NUMBERS]

    cols = math.ceil(math.sqrt(num_cams))
    rows = math.ceil(num_cams / cols)

    # Per-camera baseline
    blur_base = [0]*num_cams
    bright_base = [0]*num_cams
    noise_base = [0]*num_cams
    contrast_base = [0]*num_cams

    # Global baseline
    global_blur_hist = []
    global_bright_hist = []
    global_noise_hist = []
    global_contrast_hist = []

    # Per-camera learning hist
    blur_hist = [[] for _ in range(num_cams)]
    bright_hist = [[] for _ in range(num_cams)]
    noise_hist = [[] for _ in range(num_cams)]
    contrast_hist = [[] for _ in range(num_cams)]

    flags = [[] for _ in range(num_cams)]
    alerts = ["INIT"]*num_cams
    metrics_cache = [(0,0,0,0)]*num_cams

    print("Learning baseline (GLOBAL + LOCAL)...")


    # ==============================
    for _ in range(LEARNING_FRAMES):
        for i in range(num_cams):
            ret, frame = streams[i].read()
            if not ret:
                continue

            b, br, n, c = get_metrics(frame)

            # SAFE FILTER (critical)
            if b > 50 and br > 40:
                blur_hist[i].append(b)
                bright_hist[i].append(br)
                noise_hist[i].append(n)
                contrast_hist[i].append(c)

                global_blur_hist.append(b)
                global_bright_hist.append(br)
                global_noise_hist.append(n)
                global_contrast_hist.append(c)

        time.sleep(0.1)

    #seting the global base
    global_blur_base = np.median(global_blur_hist) if global_blur_hist else 150
    global_bright_base = np.median(global_bright_hist) if global_bright_hist else 100
    global_noise_base = np.median(global_noise_hist) if global_noise_hist else 20
    global_contrast_base = np.median(global_contrast_hist) if global_contrast_hist else 40

    #seting the camera wise base
    for i in range(num_cams):
        blur_base[i] = np.median(blur_hist[i]) if blur_hist[i] else global_blur_base
        bright_base[i] = np.median(bright_hist[i]) if bright_hist[i] else global_bright_base
        noise_base[i] = np.median(noise_hist[i]) if noise_hist[i] else global_noise_base
        contrast_base[i] = np.median(contrast_hist[i]) if contrast_hist[i] else global_contrast_base

    print("Baseline ready (GLOBAL + LOCAL)")

    last_time = time.time()

 
    while True:
        now = time.time()

        if now - last_time > CAPTURE_INTERVAL:

            for i in range(num_cams):
                ret, frame = streams[i].read()

                if not ret or frame is None:
                    alerts[i] = "NO SIGNAL"
                    continue

                blur, brightness, noise, contrast = get_metrics(frame)
                metrics_cache[i] = (blur, brightness, noise, contrast)
            
                #preventing from the value drop to zero
                safe_blur = max(blur_base[i], global_blur_base * 0.6) #0.6
                safe_bright = max(bright_base[i], global_bright_base * 0.5)
                safe_noise = max(noise_base[i], global_noise_base * 0.7)
                safe_contrast = max(contrast_base[i], global_contrast_base * 0.7)

                ratio = blur / max(safe_blur, 1e-6)

                is_blur = ratio < 0.40 or blur < global_blur_base * 0.60 #0.35 & 0.3
                is_dark = brightness < safe_bright * 0.4

                is_ir = (
                    brightness < safe_bright * 0.5 and
                    noise > safe_noise * 1.8
                )

                is_spider = (
                    noise > safe_noise * 2.5 and
                    contrast < safe_contrast * 0.6
                )

                if is_ir:
                    status = "IR FAILURE"
                elif is_spider:
                    status = "SPIDER"
                elif is_dark:
                    status = "DARK"
                elif is_blur:
                    status = "BLUR"
                else:
                    status = "OK"

                flags[i].append(status != "OK")
                if len(flags[i]) > WINDOW_SIZE:
                    flags[i].pop(0)

                if flags[i].count(True) >= THRESHOLD_COUNT:
                    alerts[i] = status
                else:
                    alerts[i] = "OK"

                    # Update baseline only when OK (exponentially weighted moving average)
                    blur_base[i] = 0.95*blur_base[i] + 0.05*blur
                    bright_base[i] = 0.95*bright_base[i] + 0.05*brightness
                    noise_base[i] = 0.95*noise_base[i] + 0.05*noise
                    contrast_base[i] = 0.95*contrast_base[i] + 0.05*contrast

                print(f"Cam {i} | Ratio:{ratio:.2f} | {alerts[i]}")

            last_time = now

        
        frames = []
        for i in range(num_cams):
            ret, frame = streams[i].read()
            if not ret or frame is None:
                frame = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)

            # cv2.putText(frame, alerts[i], (5,20),
                        
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            #             (0,255,0) if alerts[i]=="OK" else (0,0,255),1)
            # Updated putText to include Camera Number
            cv2.putText(
               frame, 
               f"CAM {CAM_NUMBERS[i]}: {alerts[i]}", # This combines the Cam No and the Alert status
               (5, 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 
               0.5, 
               (0, 255, 0) if alerts[i] == "OK" else (0, 0, 255), 1
                )

            frames.append(frame)

        while len(frames) < rows*cols:
            frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

        grid = [np.hstack(frames[r*cols:(r+1)*cols]) for r in range(rows)]
        final = np.vstack(grid)

        cv2.imshow("AI CCTV Monitor", final)

        if cv2.waitKey(1) == 27:
            break

    for s in streams:
        s.stop()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    monitor_camera()
