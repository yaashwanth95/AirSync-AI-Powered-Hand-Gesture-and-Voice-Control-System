# AirSync: AI-Powered Hand Gesture and Voice Control System

## Overview

AirSync is a Computer Vision based Human-Computer Interaction (HCI) system that allows users to control their computer using hand gestures and voice commands.

The project uses real-time hand tracking, gesture recognition, mouse automation, voice recognition, and a futuristic control panel interface to create a touchless user experience.

This project demonstrates the integration of Artificial Intelligence, Computer Vision, and Human-Computer Interaction concepts using Python and modern AI libraries.

---

## Features

### Hand Gesture Mouse Control
- Move mouse cursor using hand movements
- Smooth cursor tracking
- Real-time hand landmark detection

### Gesture-Based Click Actions
- Pinch gesture (Thumb + Index Finger) for mouse click
- Natural touchless interaction

### Drag and Drop
- Left-hand fist gesture activates mouse hold
- Release fist to drop objects

### Rotary Dial Control
- Right-hand fist enables rotary mode
- Wrist rotation performs scrolling operations
- Cursor movement is automatically locked during rotary mode

### Voice Typing
- Speech-to-text input
- Automatic text entry into active applications
- Continuous listening mode

### Real-Time AI Interface
- Live webcam feed
- Hand landmark visualization
- Futuristic Reactor Control Panel UI
- System monitoring dashboard

---

## Technologies Used

### Programming Language
- Python 3.11+

### Computer Vision
- OpenCV
- MediaPipe

### AI & Machine Learning
- MediaPipe Hand Tracking
- Speech Recognition

### GUI & Interface
- HTML
- CSS
- JavaScript
- Flask

### Automation
- PyAutoGUI
- PyDirectInput

### Audio Processing
- PyAudio
- Pygame

### Multithreading
- Python Threading

---

## Project Structure

```text
## Project Structure

AirSync-AI-Powered-Hand-Gesture-and-Voice-Control-System/
│
├── airsync.py
│   ├── Webcam Capture
│   ├── Hand Tracking Engine
│   ├── Gesture Recognition Logic
│   ├── Mouse Automation Module
│   ├── Voice Recognition Module
│   ├── Flask Streaming Server
│   └── Real-Time Video Processing
│
├── nuclear_reactor Control Panel.html
│   ├── Futuristic Dashboard UI
│   ├── Live Video Feed Display
│   ├── Control Panels
│   ├── System Monitoring Interface
│   └── Interactive Frontend Components
│
├── requirements.txt
│   └── Python Dependencies
│
├── README.md
│   └── Project Documentation
│
└── Assets (Optional)
    ├── Screenshots
    ├── Demo Videos
    └── Documentation Images


──────────────────────────────────────────────────────────────

HOW IT WORKS

[Step 1] Video Acquisition
    Webcam continuously captures live video frames using OpenCV.

[Step 2] Hand Detection
    MediaPipe detects and tracks hand landmarks in real time,
    generating 21 key points for each detected hand.

[Step 3] Gesture Recognition
    The system analyzes landmark positions to identify:

    • Cursor Movement
    • Left Click
    • Drag & Drop
    • Scroll Control
    • Rotary Mode

[Step 4] Desktop Automation
    Recognized gestures are converted into operating system actions
    using PyAutoGUI and PyDirectInput.

    Examples:
    • Move Cursor
    • Click
    • Hold & Drag
    • Scroll Up / Down

[Step 5] Voice Processing
    SpeechRecognition captures microphone input and converts
    spoken words into text for active applications.

[Step 6] Live Dashboard Streaming
    Flask streams processed video frames to the browser where
    the Reactor Control Dashboard displays the live AI interface.


──────────────────────────────────────────────────────────────

TECHNICAL WORKFLOW

Webcam
   │
   ▼
OpenCV
   │
   ▼
MediaPipe Hand Tracking
   │
   ▼
Gesture Recognition
   │
   ├── Cursor Control
   ├── Click Actions
   ├── Drag & Drop
   └── Scroll Control
   │
   ▼
PyAutoGUI / PyDirectInput
   │
   ▼
Operating System


Microphone
   │
   ▼
Speech Recognition
   │
   ▼
Voice-to-Text
   │
   ▼
Keyboard Automation


Flask Server
   │
   ▼
HTML Dashboard


──────────────────────────────────────────────────────────────

SKILLS DEMONSTRATED

• Computer Vision
• Artificial Intelligence
• Human Computer Interaction (HCI)
• Real-Time Video Processing
• Gesture Recognition
• Speech Recognition
• Desktop Automation
• Flask Web Development
• OpenCV Development
• MediaPipe Integration
• Python Programming
• System Design


──────────────────────────────────────────────────────────────

PERFORMANCE HIGHLIGHTS

• Real-Time Hand Tracking
• Low-Latency Gesture Recognition
• Smooth Cursor Mapping
• Multi-Threaded Processing
• Live Browser-Based Dashboard
• Touchless Human-Computer Interaction
• Voice-Controlled Text Input
• Lightweight and Portable Architecture
```
