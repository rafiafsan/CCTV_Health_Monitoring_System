# ==============================
# IP_BASE = "192.168.254.3"
# USER = "Admin"
# PASS = "prg@welc0me"
# CAM_NUMBERS = [1,2,3,4,5,6,7,] 

# IP_BASE = "192.168.61.10"
# USER = "PRGAI"
# PASS = "Acctv@1981"
# CAM_NUMBERS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]
# CELL_W, CELL_H = 320, 240 

import cv2
import numpy as np
import threading
import time
import math

# --- CONFIGURATION ---
RTSP_TEMPLATE = "rtsp://prgai:prgai@123@192.168.141.20:554/Streaming/Channels/{cam_no}02" # 02 for Substream, 01 for Main
CAM_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
CELL_W, CELL_H = 320, 240  # Resolution of each grid cell

class CameraStream:
    def __init__(self, cam_no):
        self.cam_no = cam_no
        self.url = RTSP_TEMPLATE.format(cam_no=cam_no)
        self.frame = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
        self.ret = False
        self.stopped = False
        
        # Start background thread to keep buffer fresh
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while not self.stopped:
            cap = cv2.VideoCapture(self.url)
            while not self.stopped:
                ret, frame = cap.read()
                if ret:
                    self.frame = cv2.resize(frame, (CELL_W, CELL_H))
                    self.ret = True
                else:
                    self.ret = False
                    break # Trigger reconnection
            cap.release()
            time.sleep(2) # Wait before reconnecting

    def stop(self):
        self.stopped = True

def main():
    streams = [CameraStream(n) for n in CAM_NUMBERS]
    
    # Calculate Grid Dimensions
    cols = math.ceil(math.sqrt(len(CAM_NUMBERS)))
    rows = math.ceil(len(CAM_NUMBERS) / cols)

    print(f"Starting viewer for {len(CAM_NUMBERS)} cameras...")

    while True:
        display_frames = []
        for i, s in enumerate(streams):
            canvas = s.frame.copy()
            
            # Add Overlay Text
            color = (0, 255, 0) if s.ret else (0, 0, 255)
            status = "LIVE" if s.ret else "RECONNECTING"
            cv2.putText(canvas, f"CH{s.cam_no}: {status}", (10, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            display_frames.append(canvas)

        # Fill empty spots in the grid
        while len(display_frames) < (rows * cols):
            display_frames.append(np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8))

        # Stitch Grid
        grid_rows = [np.hstack(display_frames[i*cols : (i+1)*cols]) for i in range(rows)]
        combined = np.vstack(grid_rows)

        cv2.imshow("Multi-Camera View", combined)
        
        if cv2.waitKey(1) & 0xFF == 27:  # Press 'ESC' to exit
            break

    for s in streams:
        s.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()