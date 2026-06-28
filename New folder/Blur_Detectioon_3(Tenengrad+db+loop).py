import cv2
import numpy as np
import time
import math
import os
import threading
import psycopg2
from psycopg2.extras import execute_batch

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"



IP_BASE = "192.168.x.x"
USER = "USER"
PASS = "PASSWORD"
CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10]

CAPTURE_INTERVAL = 3
LEARNING_FRAMES = 50

WINDOW_SIZE = 6
THRESHOLD_COUNT = 6

BATCH_SIZE =20

CELL_W, CELL_H = 320, 240

TRAINING_MODE = False

DB_CONFIG = {
    "dbname": "DBNAME",
    "user": "USER",
    "password": "PASSWORD",
    "host": "localhost",
    "port": "5432",
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_baselines():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT cam_id, blur, brightness, noise, contrast FROM camera_baseline")
        rows = cur.fetchall()
        conn.close()
        return {r[0]: r[1:] for r in rows}
    except:
        return {}
    
def clean(val):
    # If it's Not a Number or Infinity, return 0.0
    return float(val) if np.isfinite(val) else 0.

def save_baseline(cam_id, b, br, n, c):
    conn = get_conn()
    cur = conn.cursor()
    clean_cam_id = int(cam_id)
    metrics = (clean_cam_id,float(b),float(br),float(n),float(c))
    cur.execute("""
        INSERT INTO camera_baseline (cam_id, blur, brightness, noise, contrast, last_updated)
        VALUES (%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (cam_id)
        DO UPDATE SET blur=EXCLUDED.blur,
                      brightness=EXCLUDED.brightness,
                      noise=EXCLUDED.noise,
                      contrast=EXCLUDED.contrast,
                      last_updated=NOW()
    """,metrics)

    conn.commit()
    conn.close()

def save_log_alert(cam_id, alert):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO alerts (cam_id, alert_type) VALUES (%s,%s)",(cam_id,alert))
    conn.commit()
    conn.close()

def save_metrics_batch(data):
    if not data:
        return

    clean_data = []
    for row in data:
        try:
            cam_id, b, br, n, c = row
            clean_data.append((
                int(cam_id),
                float(b),
                float(br),
                float(n),
                float(c)
            ))
        except:
            continue

    if not clean_data:
        return

    conn = get_conn()
    cur = conn.cursor()

    execute_batch(cur,
        "INSERT INTO metrics_log (cam_id, blur, brightness, noise, contrast) VALUES (%s,%s,%s,%s,%s)",
        clean_data
    )

    conn.commit()
    conn.close()


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
                frame = cv2.resize(frame,(CELL_W,CELL_H))
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


def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    roi = cv2.GaussianBlur(gray,(3,3),0)

    gx = cv2.Sobel(roi, cv2.CV_64F,1,0)
    gy = cv2.Sobel(roi, cv2.CV_64F,0,1)

    blur = (gx**2 + gy**2).mean()
    brightness = np.mean(roi)
    # noise = np.std(roi)
    # contrast = roi.max() - roi.min()
    contrast = np.std(roi)
    noise = np.mean(cv2.Laplacian(roi, cv2.CV_64F))

    return blur, brightness, noise, contrast


def monitor_camera():

    BATCH_SIZE = 20
    BATCH_DURATION = 60  # seconds per batch

    # Split into batches
    batches = [CAM_NUMBERS[i:i+BATCH_SIZE] for i in range(0, len(CAM_NUMBERS), BATCH_SIZE)]

    while True:  # continuous rotation over all cameras

        for batch_cam_list in batches:

            print(f"\n===== Processing Batch: {batch_cam_list} =====")

            streams = [CameraStream(c) for c in batch_cam_list]
            num = len(batch_cam_list)

            # ==============================
            # BASELINES
            # ==============================
            blur_base = [0]*num
            bright_base = [0]*num
            noise_base = [0]*num
            contrast_base = [0]*num

            db_data = load_baselines()

            if TRAINING_MODE or len(db_data) < num:
                print("Training...")

                blur_hist = [[] for _ in range(num)]
                bright_hist = [[] for _ in range(num)]
                noise_hist = [[] for _ in range(num)]
                contrast_hist = [[] for _ in range(num)]

                for _ in range(LEARNING_FRAMES):
                    for i in range(num):
                        ret, f = streams[i].read()
                        if not ret: continue

                        b, br, n, c = get_metrics(f)

                        if b > 100 and br > 50:
                            blur_hist[i].append(b)
                            bright_hist[i].append(br)
                            noise_hist[i].append(n)
                            contrast_hist[i].append(c)

                    time.sleep(0.1)

                global_blur = np.median([v for l in blur_hist for v in l]) or 150
                global_bright = np.median([v for l in bright_hist for v in l]) or 100
                global_noise = np.median([v for l in noise_hist for v in l]) or 20
                global_contrast = np.median([v for l in contrast_hist for v in l]) or 40

                for i, cid in enumerate(batch_cam_list):
                    blur_base[i] = np.median(blur_hist[i]) if blur_hist[i] else global_blur
                    bright_base[i] = np.median(bright_hist[i]) if bright_hist[i] else global_bright
                    noise_base[i] = np.median(noise_hist[i]) if noise_hist[i] else global_noise
                    contrast_base[i] = np.median(contrast_hist[i]) if contrast_hist[i] else global_contrast

                    save_baseline(cid, blur_base[i], bright_base[i], noise_base[i], contrast_base[i])

            else:
                print("Loaded from DB")
                for i, cid in enumerate(batch_cam_list):
                    if cid in db_data:
                        blur_base[i], bright_base[i], noise_base[i], contrast_base[i] = db_data[cid]


            # ==============================
            flags = [[] for _ in range(num)]
            alerts = ["INIT"]*num
            prev = ["INIT"]*num

            last = time.time()
            last_metrics = time.time()
            batch_start = time.time()

            while time.time() - batch_start < BATCH_DURATION:

                now = time.time()

                global_blur = np.median([b for b in blur_base if b > 0]) or 150
                global_bright = np.median([b for b in bright_base if b > 0]) or 100
                global_noise = np.median([b for b in noise_base if b > 0]) or 20
                global_contrast = np.median([b for b in contrast_base if b > 0]) or 40

                if now - last > CAPTURE_INTERVAL:

                    batch_data = []

                    for i in range(num):

                        ret, f = streams[i].read()

                        if not ret:
                            alerts[i] = "NO SIGNAL"
                            continue

                        blur, bright, noise, contrast = get_metrics(f)

                        batch_data.append((batch_cam_list[i], float(blur), float(bright), float(noise), float(contrast)))

                        safe_blur = max(blur_base[i], global_blur*0.9) #0.8
                        safe_bright = max(bright_base[i], global_bright*0.5)
                        safe_noise = max(noise_base[i], global_noise*0.7)
                        safe_contrast = max(contrast_base[i], global_contrast*0.7)

                        ratio = blur / max(safe_blur, 1e-6)

                        is_blur = ratio < 0.45 and blur < 2500 and blur < global_blur*0.6  #replaced or condition with and
                        is_dark = bright < safe_bright*0.3
                        is_ir = bright < safe_bright*0.5 and noise > safe_noise*1.8
                        is_spider = noise > safe_noise*2.5 and contrast < safe_contrast*0.6

                        if is_ir: status = "IR FAILURE"
                        elif is_spider: status = "SPIDER"
                        elif is_dark: status = "DARK"
                        elif is_blur: status = "BLUR"
                        else: status = "OK"

                        flags[i].append(status != "OK")
                        if len(flags[i]) > WINDOW_SIZE:
                            flags[i].pop(0)

                        if flags[i].count(True) >= THRESHOLD_COUNT:
                            alerts[i] = status
                        else:
                            alerts[i] = "OK"

                            blur_base[i] = 0.95*blur_base[i] + 0.05*blur
                            bright_base[i] = 0.95*bright_base[i] + 0.05*bright
                            noise_base[i] = 0.95*noise_base[i] + 0.05*noise
                            contrast_base[i] = 0.95*contrast_base[i] + 0.05*contrast

                        if alerts[i] != prev[i]:
                            save_log_alert(batch_cam_list[i], alerts[i])
                            prev[i] = alerts[i]

                        print(f"Cam {batch_cam_list[i]} | {status} | Ratio:{ratio:.2f}")

                    # Save metrics every 10 sec
                    if now - last_metrics > 10:
                        try:
                            save_metrics_batch(batch_data)
                        except Exception as e:
                            print("DB insert failed:", e)
                        last_metrics = now

                    last = now

            
                frames = []

                for i in range(num):
                    ret, f = streams[i].read()

                    if not ret or f is None:
                        f = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)

                    f = cv2.resize(f, (CELL_W, CELL_H))

                    cv2.putText(f, f"CAM {batch_cam_list[i]}: {alerts[i]}",
                                (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0,255,0) if alerts[i]=="OK" else (0,0,255), 1)

                    frames.append(f)

                cols = math.ceil(math.sqrt(num))
                rows = math.ceil(num / cols)

                while len(frames) < rows*cols:
                    frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

                grid = [np.hstack(frames[r*cols:(r+1)*cols]) for r in range(rows)]
                final = np.vstack(grid)

                cv2.imshow("AI CCTV Monitor", final)

                if cv2.waitKey(1) == 27:
                    # for s in streams:
                    #     s.stop()
                    # cv2.destroyAllWindows()
                    print(f"skipping the current batch..")
                    break

            # for s in streams:
            #     s.stop()

            # cv2.destroyAllWindows()
            time.sleep(2)  
            # small gap before next batch
if __name__=="__main__":
    monitor_camera()
