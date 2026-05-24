import cv2
import numpy as np
import time
import math
import os
import threading
import psycopg2
import socket
from psycopg2.extras import execute_batch
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|timeout;5000000"
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

def is_camera_online(url, timeout=1.0):
    try:
        host_port = url.split('@')[-1].split('/')[0]
        if ':' in host_port:
            host, port = host_port.split(':')
            port = int(port)
        else:
            host = host_port
            port = 554
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

# TEST-1
# USER = "PRGAI"
# PASS = "prgai@123"
# IP_BASE = "192.168.141.2"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]

# TEST-2
# IP_BASE = "10.1.5.207"
# USER = "PRGAI"
# PASS = "P!P@prgai26"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32]

# TEST-3
# IP_BASE = "10.1.16.59"
# USER = "PRGAI"
# PASS = "PRG@ai123"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40]

# TEST-4
# IP_BASE = "192.168.186.10"
# USER = "admin"
# PASS = "brtl@98987"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40]

# TEST-5
# IP_BASE = "10.1.5.204"
# USER = "PRGAI"
# PASS = "P!P@prgai26"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20]

# TEST-6
# IP_BASE = "10.1.5.215"
# IP_BASE = "10.1.5.210"
# IP_BASE = "10.1.5.213"
# IP_BASE = "10.1.5.200"
# IP_BASE = "10.1.8.4"
# IP_BASE = "10.1.8.32"
# IP_BASE = "10.1.8.8"
# USER = "PRGAI"
# PASS = "P!P@prgai26"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20]


# stream timeout triggerd / working
# IP_BASE = "192.168.254.3"
# USER = "admin"
# PASS = "prg@welc0me"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8]

# camera acess problem
# IP_BASE = "192.168.61.10"
# USER = "PRGAI"
# PASS = "Acctv@1981"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10]

CAPTURE_INTERVAL = 5
LEARNING_FRAMES = 50

WINDOW_SIZE = 12
THRESHOLD_COUNT = 9

CELL_W, CELL_H = 320, 240

TRAINING_MODE = False

DB_CONFIG = {
    "dbname": "cctv_monitor",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432",
}

CAMERA_DB_CONFIG = {
    "dbname": "cctv_ai",
    "user": "postgres",
    "password": "123456",
    "host": '172.17.4.199', 
    "port": "5432",               
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_camera_conn():
    return psycopg2.connect(**CAMERA_DB_CONFIG)

def load_baselines():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT cam_id, blur, brightness, noise, contrast FROM camera_baseline"
        )
        rows = cur.fetchall()
        conn.close()
        return {r[0]: r[1:] for r in rows}
    except:
        return {}

def clean(val):
    # If it's Not a Number or Infinity, return 0.0
    return float(val) if np.isfinite(val) else 0.0

def save_baseline(cam_id, b, br, n, c):
    conn = get_conn()
    cur = conn.cursor()
    clean_cam_id = int(cam_id)
    metrics = (clean_cam_id, float(b), float(br), float(n), float(c))
    cur.execute(
        """
        INSERT INTO camera_baseline (cam_id, blur, brightness, noise, contrast, last_updated)
        VALUES (%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (cam_id)
        DO UPDATE SET blur=EXCLUDED.blur,
                      brightness=EXCLUDED.brightness,
                      noise=EXCLUDED.noise,
                      contrast=EXCLUDED.contrast,
                      last_updated=NOW()
    """,
        metrics,
    )

    conn.commit()
    conn.close()


def save_log_alert(cam_id, alert):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (cam_id, alert_type) VALUES (%s,%s)", (cam_id, alert)
    )
    conn.commit()
    conn.close()

def save_metrics_batch(data):
    if not data:
        return

    clean_data = []
    for row in data:
        try:
            cam_id, b, br, n, c = row
            clean_data.append((int(cam_id), float(b), float(br), float(n), float(c)))
        except:
            continue

    if not clean_data:
        return

    conn = get_conn()
    cur = conn.cursor()

    execute_batch(
        cur,
        "INSERT INTO metrics_log (cam_id, blur, brightness, noise, contrast) VALUES (%s,%s,%s,%s,%s)",
        clean_data,
    )

    conn.commit()
    conn.close()
    
def fix_rtsp_url(url):
    try:
        if "rtsp://" not in url:
            return url

        # Split into protocol + rest
        prefix, rest = url.split("rtsp://", 1)

        # Split at LAST @ (important!)
        if "@" in rest:
            creds, host = rest.rsplit("@", 1)

            # Fix only inside credentials
            creds = creds.replace("%40", "@")

            return f"rtsp://{creds}@{host}"

        return url

    except Exception as e:
        print(f"[RTSP FIX ERROR] {url} -> {e}")
        return url

init_lock = threading.Lock()

class CameraStream:
    def      __init__(self, rstp_url):
        self.url = rstp_url
        self.cap = None
        self.frame = None
        self.ret = False
        self.lock = threading.Lock()
        self.stopped = False
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        # FAST PRE-CHECK: Skip OpenCV if camera is physically unreachable
        if not is_camera_online(self.url):
            self.ret = False
            self.stopped = True
            return

        with init_lock:
            if self.stopped: return
            self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        
        failed_reads = 0
        while not self.stopped:
            if self.cap is None or not self.cap.isOpened():
                if self.cap is not None:
                    self.cap.release()
                
                time.sleep(2)
                if self.stopped or not is_camera_online(self.url):
                    continue

                with init_lock:
                    if self.stopped: break
                    self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                failed_reads = 0
                continue

            ret, frame = self.cap.read()

            if ret and frame is not None:
                failed_reads = 0
                frame = cv2.resize(frame, (CELL_W, CELL_H))
                if len(frame.shape) == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                with self.lock:
                    self.frame = frame
                    self.ret = True
            else:
                self.ret = False
                failed_reads += 1
                time.sleep(0.05)
                if failed_reads > 600:
                    self.cap.release()
                    failed_reads = 0

        # SAFE THREAD CLEANUP (Only release from the background thread)
        if self.cap is not None:
            self.cap.release()

    def read(self):
        with self.lock:
            return self.ret, self.frame

    def stop(self):
        self.stopped = True


def get_metrics(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Crop to avoid OSDs (timestamps, camera names) which inflate gradient/blur metrics
    h, w = gray.shape
    ch, cw = int(h * 0.25), int(w * 0.20)
    roi_gray = gray[ch:h-ch, cw:w-cw]
    
    roi = cv2.GaussianBlur(roi_gray, (3, 3), 0)

    gx = cv2.Sobel(roi, cv2.CV_64F, 1, 0)
    gy = cv2.Sobel(roi, cv2.CV_64F, 0, 1)

    blur = (gx**2 + gy**2).mean()
    brightness = np.mean(roi)
    # noise = np.std(roi)
    # contrast = roi.max() - roi.min()
    contrast = np.std(roi)
    noise = np.mean(cv2.Laplacian(roi, cv2.CV_64F))

    return blur, brightness, noise, contrast


def save_snapshot(cam_id, cam_name, frame):

    SNAPSHOT_DIR = "C:\\Users\\USER\\Desktop\\cctv_blur_detection\\Blurr_Signals"
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    try:
        # SNAPSHOT_DIR = "C:\\Users\\USER\\Desktop\\cctv_blur_detection\\snapshoots"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{cam_id}_{cam_name}_{timestamp}.jpg"
        filepath = os.path.join(SNAPSHOT_DIR, filename)

        cv2.imwrite(filepath, frame)
        print(f"[SNAPSHOT SAVED] {filepath}")

    except Exception as e:
        print("Snapshot error:", e)

def fetch_camera_master():
    conn = get_camera_conn()

    print("Database connected.") 

    cur = conn.cursor()

    cur.execute("""
        SELECT id, camera_name, rtsp
        FROM camera
        ORDER BY id
    """)

    rows = cur.fetchall()
    print("All rows fetched.")
    conn.close()

    camera_list = []
    for r in rows:
        camera_list.append({
            "id": r[0],
            "camera_name": r[1],
            "rtsp": r[2]
        })

    print(f"[INFO] Loaded {len(camera_list)} cameras from REMOTE DB")
    return camera_list

def generate_no_signal_image(cam_id, cam_name):

    width = 320
    height =240
    
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    text = "NO SIGNAL"
    
    font_paths = [
        "arial.ttf",      # Common on Windows, macOS
        "DejaVuSans.ttf",  # Common on Linux
        "Courier New.ttf"   # Monospace
    ]

    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, height // 10) 
            break
        except OSError:
            continue

    if font is None:
        print("Warning: Could not find a suitable system font. Using the default small font.")
        font = ImageFont.load_default()


    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2

    draw.text((text_x, text_y), text, fill=(200, 200, 200), font=font)

    info_text = f"ID: {cam_id} | Name: {cam_name}"
    draw.text((10, 10), info_text, fill=(255, 255, 255), font=font)

    # 5. Save the image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{cam_id}_{cam_name}_{timestamp}.jpg"
    snap_dir = "C:\\Users\\USER\\Desktop\\cctv_blur_detection\\No_Singals"
    save_path = os.path.join(snap_dir, filename)
    image.save(save_path)
    print(f"Image saved to: {save_path}")

def monitor_camera():
    print(f"Monitor camera started.")
    BATCH_SIZE = 16
    BATCH_DURATION = 90

    camera_master = fetch_camera_master()

    batches = [
        camera_master[i:i+BATCH_SIZE]
        for i in range(0, len(camera_master), BATCH_SIZE)
    ]

    while True:

        for batch_cam_list in batches:

            print(f"\n===== Processing Batch: {[c['id'] for c in batch_cam_list]} =====")
            print(batch_cam_list[0])
            print(batch_cam_list[0]['rtsp'])
            # streams_n = CameraStream(batch_cam_list[0]['rtsp'])

            streams = [CameraStream(cam["rtsp"]) for cam in batch_cam_list]
            num = len(batch_cam_list)

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
                        if not ret:
                            continue

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

                for i, cam in enumerate(batch_cam_list):

                    blur_base[i] = np.median(blur_hist[i]) if blur_hist[i] else global_blur
                    bright_base[i] = np.median(bright_hist[i]) if bright_hist[i] else global_bright
                    noise_base[i] = np.median(noise_hist[i]) if noise_hist[i] else global_noise
                    contrast_base[i] = np.median(contrast_hist[i]) if contrast_hist[i] else global_contrast

                    save_baseline(
                        cam["id"],
                        blur_base[i],
                        bright_base[i],
                        noise_base[i],
                        contrast_base[i],
                    )

            else:
                print("Loaded from DB")

                for i, cam in enumerate(batch_cam_list):
                    cid = cam["id"]
                    if cid in db_data:
                        blur_base[i], bright_base[i], noise_base[i], contrast_base[i] = db_data[cid]

            flags = [[] for _ in range(num)]
            alerts = ["INIT"]*num
            prev = ["INIT"]*num
            no_signal_image_generated = [False] * num

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

                        cam = batch_cam_list[i]

                        ret, f = streams[i].read()

                        if not ret:
                            if prev[i] != "NO SIGNAL":
                              save_log_alert(cam["id"], "NO SIGNAL")
                            prev[i] = "NO SIGNAL"
                            alerts[i] = "NO SIGNAL"
                            
                            if (now - batch_start >= BATCH_DURATION - 10) and not no_signal_image_generated[i]:
                                generate_no_signal_image(cam['id'],cam['camera_name'])
                                no_signal_image_generated[i] = True
                                
                            print(f"camid: {cam['id']} name: {cam['camera_name']} -> NO SIGNAL")
                            continue

                        blur, bright, noise, contrast = get_metrics(f)

                        batch_data.append((
                            cam["id"],
                            float(blur),
                            float(bright),
                            float(noise),
                            float(contrast),
                        ))

                        safe_blur = max(blur_base[i], global_blur * 0.9)
                        safe_bright = max(bright_base[i], global_bright * 0.5)
                        safe_noise = max(noise_base[i], global_noise * 0.7)
                        safe_contrast = max(contrast_base[i], global_contrast * 0.7)

                        ratio = blur / max(safe_blur, 1e-6)

                        is_solid = contrast < 5.0
                        is_blur = ratio < 0.45 and blur < 2500 and blur < global_blur * 0.6
                        is_dark = bright < safe_bright * 0.3
                        is_ir = bright < safe_bright * 0.5 and noise > safe_noise * 1.8
                        is_spider = noise > safe_noise * 2.5 and contrast < safe_contrast * 0.6

                        if is_solid:
                            status = "LOW BW"
                        elif is_ir:
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

                            blur_base[i] = 0.95*blur_base[i] + 0.05*blur
                            bright_base[i] = 0.95*bright_base[i] + 0.05*bright
                            noise_base[i] = 0.95*noise_base[i] + 0.05*noise
                            contrast_base[i] = 0.95*contrast_base[i] + 0.05*contrast

                        if alerts[i] != prev[i]:

                            save_log_alert(cam["id"], alerts[i])

                            if alerts[i] == "BLUR" or alerts[i] == "DARK" or alerts[i] == "IR FAILURE" or alerts[i] == "SPIDER":
                                ret_snap, frame_snap = streams[i].read()
                                if ret_snap:
                                    save_snapshot(cam["id"], cam["camera_name"], frame_snap)
                            prev[i] = alerts[i]

                        print(f"camid: {cam['id']} name: {cam['camera_name']} | {status} | ratio:{ratio:.2f}")

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

                    cam = batch_cam_list[i]

                    cv2.putText(
                        f,
                        f"{cam['id']}:{alerts[i]}",
                        (5, 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0,255,0) if alerts[i]=="OK" else (0,0,255),
                        1
                    )

                    frames.append(f)

                cols = math.ceil(math.sqrt(num))
                rows = math.ceil(num / cols)

                while len(frames) < rows * cols:
                    frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

                grid = [np.hstack(frames[r*cols:(r+1)*cols]) for r in range(rows)]
                final = np.vstack(grid)

                cv2.imshow("AI CCTV Monitor", final)

                if cv2.waitKey(1) == 27:
                    print("Skipping batch...")
                    break

            # Cleanup previous streams before moving to next batch
            for stream in streams:
                stream.stop()

            time.sleep(2)

if __name__ == "__main__":
    monitor_camera()
