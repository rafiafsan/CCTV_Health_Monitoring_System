
# 🎥 CCTV Health Monitoring System

<p align="center">
  <img src="cctv_health_monitoring_workflow.png" alt="CCTV Health Monitoring System Banner" width="100%">
</p>

> A production-grade AI-powered CCTV Health Monitoring System that continuously monitors the operational health of multiple CCTV cameras by analyzing image quality, network reachability, and stream availability in real time.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-red.svg)
![Multi-Threading](https://img.shields.io/badge/Multi--Threading-Enabled-success.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

# Table of Contents

- Overview
- Features
- Business Problem
- Solution Overview
- System Workflow
- Architecture
- Folder Structure
- Technologies Used
- Processing Pipeline
- Health Monitoring Logic
- Image Quality Metrics
- Camera Status Detection
- Database Design
- Installation
- Configuration
- Running the System
- Logging
- Dashboard
- Performance
- Future Improvements
- License

---

# Overview

The **AI CCTV Health Monitoring System** is designed to automatically monitor the operational health of hundreds of CCTV cameras deployed across industrial facilities, campuses, smart cities, factories, and surveillance infrastructures.

Instead of detecting objects or people, this system continuously evaluates whether each camera is functioning properly by analyzing:

- Camera reachability
- RTSP connectivity
- Live video availability
- Image blur
- Image brightness
- Image noise
- Image contrast
- Network quality
- Stream failures

When abnormal conditions are detected, the system automatically generates alerts, stores evidence snapshots, logs monitoring metrics, and updates the monitoring dashboard.

---

# Key Features

## Multi-Camera Monitoring

- Supports hundreds of RTSP cameras
- Configurable batch processing
- Multi-threaded camera handling
- Continuous monitoring loop

---

## Camera Reachability Monitoring

Before opening any video stream, the system checks:

- Network connectivity
- IP accessibility
- Camera availability
- RTSP readiness

Offline cameras are immediately logged without interrupting other monitoring tasks.

---

## AI-Based Image Quality Analysis

Every captured frame is analyzed using computer vision metrics.

The system measures:

- Blur
- Brightness
- Noise
- Contrast

These measurements are compared with each camera's learned baseline to detect abnormalities.

---

## Automatic Baseline Learning

For newly added cameras:

- Collects multiple frames
- Calculates median quality values
- Stores baseline metrics
- Uses baseline for future comparisons

No manual calibration is required.

---

## Intelligent Alerting

Alerts are only generated after abnormal conditions persist over multiple frames using a sliding window decision mechanism.

This minimizes false alarms caused by temporary disturbances.

---

## Live Monitoring Dashboard

Displays:

- Live camera feeds
- Camera health status
- Camera name
- Camera ID
- Status color
- Snapshots
- Monitoring information

---

## Automatic Logging

Every monitoring cycle stores:

- Camera metrics
- Reachability logs
- Camera status
- Alerts
- Timestamps

---

# Business Problem

Large organizations often deploy hundreds or thousands of CCTV cameras.

Common issues include:

- Cameras going offline
- Blurry images
- Dirty lenses
- Spider webs
- Dark images
- Network degradation
- Hardware failures

Without automated monitoring, these problems often remain unnoticed until critical incidents occur.

This system provides continuous automated health monitoring to ensure surveillance systems remain operational.

---

# Solution Overview

The monitoring pipeline performs the following tasks:

1. Load active cameras
2. Resume monitoring from the previous traversal
3. Divide cameras into batches
4. Check camera reachability
5. Open RTSP streams
6. Capture frames
7. Analyze image quality
8. Compare against baseline
9. Determine camera status
10. Generate alerts if necessary
11. Store metrics
12. Display monitoring dashboard
13. Continue monitoring

---

# System Workflow

![Workflow](docs/workflow.png)

High-Level Flow

```
System Start

↓

Load Camera Configuration

↓

Load Camera List

↓

Divide Into Batches

↓

Check Camera Reachability

↓

Open RTSP Streams

↓

Capture Frames

↓

Compute Image Quality Metrics

↓

Compare With Baseline

↓

Determine Camera Health

↓

Sliding Window Decision

↓

Generate Alerts

↓

Save Metrics

↓

Display Dashboard

↓

Load Next Batch

↓

Repeat
```

---

# System Architecture

```
                PostgreSQL
                     │
                     │
          Camera Configuration
                     │
                     ▼
         Multi-Thread Batch Manager
                     │
                     ▼
        Camera Reachability Check
                     │
         ┌───────────┴─────────────┐
         │                         │
         ▼                         ▼
 Offline Camera             Online Camera
         │                         │
         ▼                         ▼
   Log Offline Status       Open RTSP Stream
                                   │
                                   ▼
                           Capture Video Frame
                                   │
                                   ▼
                      Image Quality Analysis
                                   │
                                   ▼
                        Baseline Comparison
                                   │
                                   ▼
                     Camera Status Classification
                                   │
                                   ▼
                      Alert Decision Engine
                                   │
                                   ▼
                 Logging & Live Dashboard
```

---

# Folder Structure

```
CCTV-Health-Monitoring-System/

│
├── screenshots/
│
├── config/
│
├── models/
│
├── database/
│
├── monitoring.py
│
├── load_camera.py
│
├── requirements.txt
│
├── README.md
│
└── docs/
      workflow.png
```

---

# Technologies Used

| Technology | Purpose |
|------------|----------|
| Python | Core application |
| OpenCV | Video processing |
| PostgreSQL | Database |
| NumPy | Image analysis |
| Multi-threading | Parallel camera processing |
| RTSP | Live camera streaming |

---

# Processing Pipeline

```
Load Camera

↓

Check Reachability

↓

Open RTSP Stream

↓

Read Frame

↓

Resize

↓

Compute Metrics

↓

Compare Baseline

↓

Classify Status

↓

Alert Decision

↓

Store Logs

↓

Display Dashboard
```

---

# Image Quality Metrics

The following image quality indicators are computed for every frame.

## Blur

Measured using:

```
Variance of Laplacian
```

Detects:

- Out-of-focus cameras
- Dirty lenses
- Motion blur

---

## Brightness

Measured using:

```
Mean Pixel Intensity
```

Detects:

- Low lighting
- Overexposure
- Camera obstruction

---

## Noise

Measured using:

```
Standard Deviation
```

Detects:

- Sensor degradation
- Poor signal quality
- Compression artifacts

---

## Contrast

Measured using:

```
Root Mean Square (RMS)
```

Detects:

- Foggy images
- Low visibility
- Image fading

---

# Camera Status Classification

The system classifies each camera into one of the following states.

| Status | Description |
|---------|-------------|
| 🟢 OK | Camera operating normally |
| 🟡 Blur | Image out of focus |
| 🟠 Dark | Low brightness |
| 🔴 IP Failure | Camera unreachable |
| 🟣 Spider Web | Lens obstruction detected |
| 🔵 Low Bandwidth | Poor stream quality |
| ⚫ No Signal | RTSP stream unavailable |

---

# Baseline Learning

For new cameras:

1. Capture multiple frames
2. Compute quality metrics
3. Calculate median values
4. Store baseline in database

Future frames are compared against these learned baseline values.

---

# Alert Decision Logic

The system uses a **sliding window** approach to reduce false alarms.

Example:

```
Window Size = 12 Frames

↓

Abnormal Frames ≥ Threshold

↓

Generate Alert

↓

Save Snapshot

↓

Update Status
```

Temporary image fluctuations do not trigger alerts.

---

# Database Design

## Camera Database

### camera

Stores camera configuration.

- Camera ID
- Camera Name
- RTSP URL
- NVR IP
- Active Status

---

### category_wise_status

Stores monitoring traversal progress.

---

### camera_reachability_history

Stores online/offline logs.

---

### camera_status

Stores current health status.

---

## Monitoring Database

### camera_baseline

Stores learned image quality baselines.

---

### camera_metrics

Stores image quality metrics collected over time.

---

### alerts

Stores generated alerts and snapshot locations.

---

# Installation

Clone repository

```bash
git clone https://github.com/yourusername/CCTV-Health-Monitoring-System.git
```

Enter directory

```bash
cd CCTV-Health-Monitoring-System
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Configure the monitoring parameters.

Example

```python
BATCH_SIZE = 8

CAPTURE_INTERVAL = 5

WINDOW_SIZE = 12

THRESHOLD_COUNT = 9
```

Database credentials and camera configuration should be updated in the configuration files.

---

# Running the System

Start monitoring using

```bash
python monitoring.py
```

---

# Logging

The system continuously stores:

- Reachability logs
- Camera metrics
- Alert history
- Camera status
- Monitoring timestamps

All logs are persisted in PostgreSQL for historical analysis.

---

# Live Dashboard

The monitoring dashboard displays:

- Multi-camera grid view
- Live snapshots
- Camera name
- Camera ID
- Health status
- Monitoring color indicators
- Current FPS (if available)

---

# Performance

Designed for enterprise-scale deployments.

Optimizations include:

- Multi-threaded camera processing
- Batch-based monitoring
- Automatic baseline learning
- Sliding window alert filtering
- PostgreSQL logging
- Real-time dashboard
- Automatic traversal recovery
- Fault-tolerant camera handling

---

# Future Improvements

- Web-based monitoring dashboard
- Email notifications
- SMS alerts
- Telegram integration
- Microsoft Teams alerts
- GPU acceleration
- Docker deployment
- Kubernetes support
- REST API
- Historical analytics dashboard
- Predictive camera failure detection
- Grafana integration
- Prometheus monitoring
- Cloud deployment support

---

# License

This project is licensed under the MIT License.

---

# Author

**Rafi Afsan**

AI Engineer | Computer Vision | Intelligent Video Analytics | AI Surveillance Systems

---

## ⭐ If you find this project useful, consider giving it a star on GitHub.
