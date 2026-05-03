import cv2
import numpy as np
import time
import math
import os
import threading

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"

# --- CONFIGURATION ---
# USER = "PRGAI"
# PASS = "prgai@123"
# IP_BASE = "192.168.141.2"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

# IP_BASE = "192.168.61.10"
# USER = "PRGAI"
# PASS = "Acctv@1981"
# CAM_NUMBERS = [8]

# IP_BASE = "10.1.5.207"
# USER = "PRGAI"
# PASS = "P!P@prgai26"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]

IP_BASE = "192.168.186.10"
USER = "amin"
PASS = "brtl@98987"
CAM_NUMBERS = "1,2,3,4,5,6,7,8"

# IP_BASE = "10.1.16.59"
# USER = "PRGAI"
# PASS = "PRG@ai123"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

# IP_BASE = "192.168.254.3"
# USER = "Admin"
# PASS = "prg@welc0me"
# CAM_NUMBERS = [1,2,3,4,5,6,7,]


CAPTURE_INTERVAL = 5
LEARNING_FRAMES = 20
ALPHA = 0.1
WINDOW_SIZE = 12
THRESHOLD_COUNT = 12
CELL_W, CELL_H = 320, 240

# --- ABSOLUTE THRESHOLDS ---
#80,50,80,35 - recommended
MIN_BLUR = 80
MIN_BRIGHTNESS = 50
MAX_NOISE = 80
MIN_CONTRAST = 29


class CameraStream:
    def __init__(self, cam_no):
        self.cam_no = cam_no
        self.url = f"rtsp://{USER}:{PASS}@{IP_BASE}:554/Streaming/Channels/{cam_no}02"

        self.cap = cv2.VideoCapture(self.url)
        self.ret = False
        self.frame = None
        self.stopped = False

        self.lock = threading.Lock()
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


def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    blur = cv2.Laplacian(gray, cv2.CV_64F).var() #measureed by the distance of edges
    brightness = np.mean(gray)
    noise = np.std(gray)
    contrast = np.std(gray)

    return blur, brightness, noise, contrast


def draw_overlay(frame, blur, brightness, noise, contrast, cam_idx, status):
    overlay = frame.copy()
    color = (0, 255, 0) if "OK" in status else (0, 0, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX

    cv2.rectangle(overlay, (0, 0), (140, 60), (0, 0, 0), -1)
    cv2.putText(overlay, f"B:{blur:.0f}", (5, 12), font, 0.35, (0, 255, 0), 1)
    cv2.putText(overlay, f"L:{brightness:.0f}", (5, 25), font, 0.35, (0, 255, 0), 1)
    cv2.putText(overlay, f"N:{noise:.0f}", (5, 38), font, 0.35, color, 1)
    cv2.putText(overlay, f"C:{contrast:.0f}", (5, 52), font, 0.35, color, 1)

    cv2.rectangle(overlay, (0, CELL_H-25), (CELL_W, CELL_H), (0, 0, 0), -1)
    cv2.putText(overlay, f"CAM {CAM_NUMBERS[cam_idx]}: {status}",
                (5, CELL_H-8), font, 0.4, color, 1)

    return cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)



def monitor_camera():
    num_cams = len(CAM_NUMBERS)

    cols = math.ceil(math.sqrt(num_cams))
    rows = math.ceil(num_cams / cols)

    print(f"Initializing {num_cams} cameras...")

    streams = [CameraStream(n) for n in CAM_NUMBERS]

    blur_flags = [[] for _ in range(num_cams)]
    dark_flags = [[] for _ in range(num_cams)]
    ir_flags = [[] for _ in range(num_cams)]
    lost_flags = [[] for _ in range(num_cams)]

    blur_means = [0.0] * num_cams
    bright_means = [0.0] * num_cams
    noise_means = [0.0] * num_cams
    contrast_means = [0.0] * num_cams

    valid_counts = [0] * num_cams
    baseline_ready = [False] * num_cams

    current_alerts = ["INIT"] * num_cams
    metrics_cache = [(0, 0, 0, 0)] * num_cams

    time.sleep(2)

   
    print("Learning baseline...")
    for _ in range(LEARNING_FRAMES):
        for i in range(num_cams):
            ret, frame = streams[i].read()
            if ret:
                b, br, n, c = get_metrics(frame)
                #learn if the frame is good and clear enough
                if b > MIN_BLUR and br > MIN_BRIGHTNESS and n < MAX_NOISE and c > MIN_CONTRAST:
                    blur_means[i] += b
                    bright_means[i] += br
                    noise_means[i] += n
                    contrast_means[i] += c
                    valid_counts[i] += 1
        time.sleep(0.1)
        print(f'b_mean:{blur_means} br_mean:{bright_means} n_mean:{noise_means} c_mean:{contrast_means}\n')
    
    
    for i in range(num_cams):
        if valid_counts[i] > 0:
            blur_means[i] /= valid_counts[i]
            bright_means[i] /= valid_counts[i]
            noise_means[i] /= valid_counts[i]
            contrast_means[i] /= valid_counts[i]
            baseline_ready[i] = True
        else:
            blur_means[i] = 150
            bright_means[i] = 80
            noise_means[i] = 20
            contrast_means[i] = 50

    print("Baseline ready")

    last_check_time = time.time()

   
    while True:
        processed_frames = []
        current_time = time.time()

        if current_time - last_check_time > CAPTURE_INTERVAL:

            for i in range(num_cams):
                ret, frame = streams[i].read()

                if not ret or frame is None:
                    blur, brightness, noise, contrast = 0, 0, 0, 0
                    is_lost = True
                else:
                    blur, brightness, noise, contrast = get_metrics(frame)
                    is_lost = False

                metrics_cache[i] = (blur, brightness, noise, contrast)

                # ==============================
                # ABSOLUTE
                # ==============================
                abs_blurry = blur < MIN_BLUR
                abs_dark = brightness < MIN_BRIGHTNESS
                abs_noise = noise > MAX_NOISE
                abs_hazy = contrast < MIN_CONTRAST

                # ==============================
                # RELATIVE
                # ==============================
                #can be tunnend according to the env and needs
                rel_blurry = blur < blur_means[i] * 0.6
                rel_dark = brightness < bright_means[i] * 0.3
                rel_ir = brightness < bright_means[i] * 0.4 and noise > noise_means[i] * 1.5
                rel_hazy = contrast < contrast_means[i] * 0.5

                is_blurry = abs_blurry or rel_blurry or abs_hazy or rel_hazy
                is_dark = abs_dark or rel_dark
                is_ir_fail = abs_noise or rel_ir

                # update flags
                blur_flags[i].append(is_blurry)
                dark_flags[i].append(is_dark)
                ir_flags[i].append(is_ir_fail)
                lost_flags[i].append(is_lost)

                if len(blur_flags[i]) > WINDOW_SIZE:
                    blur_flags[i].pop(0)
                    dark_flags[i].pop(0)
                    ir_flags[i].pop(0)
                    lost_flags[i].pop(0)

                blur_count = sum(blur_flags[i])
                dark_count = sum(dark_flags[i])
                ir_count = sum(ir_flags[i])
                lost_count = sum(lost_flags[i])

                # ==============================
                # FINAL DECISION
                # ==============================
                if lost_count >= THRESHOLD_COUNT:
                    current_alerts[i] = "No Signal"
                elif ir_count >= THRESHOLD_COUNT:
                    current_alerts[i] = "IR/Spider"
                elif blur_count >= THRESHOLD_COUNT:
                    current_alerts[i] = "Blurry/Hazy"
                elif dark_count >= THRESHOLD_COUNT:
                    current_alerts[i] = "Dark"
                else:
                    current_alerts[i] = "OK"

                    #only learn if the frame is good and clear enough
                    is_clean = (
                        blur > MIN_BLUR and
                        brightness > MIN_BRIGHTNESS and
                        noise < MAX_NOISE and
                        contrast > MIN_CONTRAST
                    )

                    if baseline_ready[i] and is_clean:
                        blur_means[i] = (1 - ALPHA) * blur_means[i] + ALPHA * blur
                        bright_means[i] = (1 - ALPHA) * bright_means[i] + ALPHA * brightness
                        noise_means[i] = (1 - ALPHA) * noise_means[i] + ALPHA * noise
                        contrast_means[i] = (1 - ALPHA) * contrast_means[i] + ALPHA * contrast
                    print(f"Cam{i} -> Blur:{blur:.1f}, Bright:{brightness:.1f}, Noise:{noise:.1f}, Contrast:{contrast:.1f}")

            last_check_time = current_time

        
        for i in range(num_cams):
            ret, frame = streams[i].read()

            if not ret or frame is None:
                frame = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
                cv2.putText(frame, "LOST SIGNAL",
                            (60, CELL_H // 2),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 0, 255), 2)
                blur, brightness, noise, contrast = 0, 0, 0, 0
            else:
                blur, brightness, noise, contrast = metrics_cache[i]

            processed_frames.append(
                draw_overlay(frame, blur, brightness, noise, contrast, i, current_alerts[i])
            )

        while len(processed_frames) < (rows * cols):
            processed_frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

        grid_rows = []
        for r in range(rows):
            row_data = processed_frames[r * cols:(r + 1) * cols]
            grid_rows.append(np.hstack(row_data))

        final_grid = np.vstack(grid_rows)

        display_w = min(1920, cols * CELL_W)
        display_h = int(display_w * (final_grid.shape[0] / final_grid.shape[1]))

        cv2.imshow("Camera Monitor", cv2.resize(final_grid, (display_w, display_h)))

        if cv2.waitKey(1) & 0xFF == 27:
            break

    for s in streams:
        s.stop()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    monitor_camera()