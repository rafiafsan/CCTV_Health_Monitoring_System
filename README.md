# AI CCTV Monitoring & Animal Detection System

<p align="center">
  <img src="docs/workflow.png" width="900">
</p>

## Overview

The **AI CCTV Monitoring & Animal Detection System** is an intelligent surveillance platform designed to continuously monitor hundreds of CCTV cameras in real-time. The system automatically detects camera health issues such as:

- Blur
- Darkness
- IR Failure
- Spider Web obstruction
- Low Bandwidth / Frozen Image
- No Signal
- Animal Detection (YOLO)

Unlike traditional monitoring systems that rely on human operators, this system performs continuous AI-based analysis of every camera feed and immediately generates alerts whenever abnormalities are detected.

The system is designed for large industrial environments, factories, warehouses, power plants, and enterprise CCTV infrastructures where manual monitoring of hundreds of cameras is impractical.

---

# Features

## Camera Health Monitoring

The system continuously evaluates every camera by analyzing image quality metrics.

Detects:

- Blur
- Darkness
- IR Failure
- Spider Web
- Low Bandwidth
- No Signal

---

## Animal Detection

Using YOLO, the system detects animals entering restricted areas.

Supported classes include:

- Dog
- Cat
- Cow
- Goat
- Horse
- Bird
- Other supported YOLO classes

When an animal is detected:

- Snapshot is captured
- Detection is logged
- Alert is generated
- Confidence score is stored

---

## Intelligent Baseline Learning

Instead of using fixed thresholds, every camera learns its own normal operating condition.

Metrics learned:

- Blur
- Brightness
- Noise
- Contrast

The baseline is stored inside PostgreSQL and updated dynamically over time.

---

## Batch Camera Processing

Monitoring hundreds of RTSP streams simultaneously is computationally expensive.

Instead, cameras are processed in configurable batches.

Example:

```
Batch Size = 8 Cameras

Batch 1:
Camera 1-8

↓

Batch 2:
Camera 9-16

↓

Batch 3:
Camera 17-24
```

This significantly reduces:

- CPU usage
- RAM consumption
- GPU utilization
- RTSP connection overhead

---

## Live Monitoring Dashboard

The system provides a real-time dashboard displaying:

- Live camera stream
- Camera ID
- Camera Name
- Current status
- Color-coded alerts
- Remaining batch processing time

Example:

```
+------------+------------+
| Cam 1 OK   | Cam 2 Blur |
+------------+------------+
| Cam 3 Dark | Cam 4 OK   |
+------------+------------+
```

---

# System Architecture

```
                        PostgreSQL
                     (Camera Database)
                            │
                            │
                            ▼
                 Load Camera Information
                            │
                            ▼
                  RTSP Camera Connections
                            │
                            ▼
                 Multi-thread Camera Streams
                            │
                            ▼
                  Frame Acquisition (OpenCV)
                            │
                            ▼
               Image Quality Metric Extraction
                            │
            ┌───────────────┼────────────────┐
            │               │                │
            ▼               ▼                ▼
      Blur Detection   Animal Detection   Health Check
            │               │                │
            └───────────────┼────────────────┘
                            ▼
                  Decision Making Engine
                            │
            ┌───────────────┼────────────────┐
            ▼               ▼                ▼
       Alert Logs     Snapshot Save     Dashboard
                            │
                            ▼
                     PostgreSQL Database
```

---

# Workflow

## Step 1

Start Application

↓

Load configuration

↓

Connect to PostgreSQL

---

## Step 2

Load Camera List

The application retrieves

- Camera ID
- Camera Name
- RTSP URL

from the Camera Database.

---

## Step 3

Resume Previous Traversal

The last processed camera ID is loaded from

```
category_wise_status
```

This allows the application to continue from where it previously stopped.

---

## Step 4

Divide Cameras into Batches

Example

```
Total Cameras = 240

Batch Size = 8

240 / 8

=

30 batches
```

---

## Step 5

Initialize Camera Threads

Each camera runs in an independent thread.

```
Camera 1
Thread 1

Camera 2
Thread 2

Camera 3
Thread 3
```

---

## Step 6

Check Camera Reachability

Before opening RTSP,

the system performs a socket connection.

If unreachable:

```
NO SIGNAL
```

is immediately reported.

---

## Step 7

Open RTSP Stream

If reachable

↓

OpenCV VideoCapture

↓

Continuous Frame Reading

---

## Step 8

Extract Image Metrics

Every frame computes

### Blur

Using Sobel Gradient

### Brightness

Mean Intensity

### Noise

Laplacian

### Contrast

Standard Deviation

---

## Step 9

Baseline Learning

If the camera has no previous baseline,

the system learns

50 frames

and computes

Median Blur

Median Brightness

Median Noise

Median Contrast

These values become the camera's baseline.

---

## Step 10

Status Classification

The system compares current metrics against baseline.

Possible results:

```
OK

BLUR

DARK

IR FAILURE

SPIDER WEB

LOW BANDWIDTH

NO SIGNAL
```

---

## Step 11

Sliding Window Validation

To avoid false alarms

WINDOW_SIZE = 12

THRESHOLD = 9

Only if

9 of last 12 frames

are abnormal

↓

Alert generated

---

## Step 12

Save Alert

Database:

```
alerts
```

Information stored:

- Camera ID
- Alert Type
- Timestamp

---

## Step 13

Capture Snapshot

For

- Blur
- Dark
- Spider
- IR Failure

the current frame is saved automatically.

---

## Step 14

Save Metrics

Every 10 seconds

the following are stored

```
Blur

Brightness

Noise

Contrast
```

for historical analysis.

---

## Step 15

Display Dashboard

The operator sees

- Live Stream
- Alert Status
- Camera ID
- Camera Name

---

## Step 16

Move to Next Batch

After

90 seconds

↓

Stop current streams

↓

Open next batch

---

## Database Design

### Camera Database

Contains

```
camera
```

Stores

- Camera ID
- Name
- RTSP
- Factory
- Department

---

### camera_baseline

Stores learned values

```
Blur

Brightness

Noise

Contrast
```

---

### alerts

Stores every alert generated.

Columns

```
id

camera_id

alert_type

timestamp
```

---

### metrics_log

Stores periodic metric values.

Useful for analytics.

---

### camera_reachability_history

Stores

```
Camera ID

Reachable

Timestamp
```

---

### category_wise_status

Stores

```
Last Traversed Camera

Current Category

Resume Information
```

---

# Folder Structure

```
AI-CCTV-Monitoring/
│
├── models/
│      YOLO weights
│
├── snapshots/
│
├── no_signal/
│
├── docs/
│      workflow.png
│      architecture.png
│
├── database/
│      schema.sql
│
├── utils/
│      load_camera.py
│
├── monitor.py
│
├── animal_detection.py
│
├── requirements.txt
│
└── README.md
```

---

# Technologies Used

| Component | Technology |
|------------|------------|
| Programming Language | Python |
| AI Detection | YOLO (Ultralytics) |
| Computer Vision | OpenCV |
| Database | PostgreSQL |
| Image Processing | NumPy |
| Snapshot | Pillow |
| Threading | Python Threading |
| Networking | Socket |
| Database Driver | Psycopg2 |

---

# Performance Optimizations

- Multi-threaded camera streaming
- Batch processing
- Dynamic baseline adaptation
- Sliding window filtering
- Bulk database insertion
- Socket-based reachability checking
- Automatic reconnection
- Frame resizing
- Adaptive thresholds

---

# Future Improvements

- Web Dashboard
- Email Notifications
- SMS Alerts
- WhatsApp Alerts
- Telegram Alerts
- REST API
- Docker Deployment
- Kubernetes Support
- Prometheus Monitoring
- Grafana Dashboard
- GPU Multi-stream Inference
- Distributed Camera Processing
- Face Detection
- PPE Detection
- Vehicle Detection
- Fire & Smoke Detection
- Intrusion Detection

---

# Advantages

- Fully automated camera health monitoring
- AI-powered animal detection
- Scalable to hundreds of cameras
- Database-driven architecture
- Robust against temporary failures
- Low false alarm rate
- Easy integration with existing CCTV infrastructure

---

# Author

Developed as an intelligent AI surveillance solution for industrial-scale CCTV monitoring using modern Computer Vision and Deep Learning techniques.
