import math
import time
import datetime
import os
import threading

# Authentication State
auth_authenticated = False
auth_current_step = 0  # 0: Open Palm, 1: Closed Fist, 2: CW Rotation, 3: Pinch, 4: Authenticated
auth_failed_attempts = 0
auth_time_left = 30.0
auth_hard_locked = False
auth_active = False
auth_start_time = 0.0
auth_logs = ["Challenge waiting to start..."]
auth_lock = threading.Lock()

# Clockwise Rotation Tracking
prev_hand_angle = None
accumulated_cw_rotation = 0.0

def log_auth_event(msg, status="info"):
    global auth_logs
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    with auth_lock:
        auth_logs.append(formatted_msg)
        if len(auth_logs) > 50:
            auth_logs.pop(0)
    
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "auth_logs.txt")
        with open(log_path, "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] [{status.upper()}] {msg}\n")
    except Exception as e:
        print(f"Error writing to auth log file: {e}")

def is_open_palm_gesture(lms):
    index_up = lms.landmark[8].y < lms.landmark[6].y
    middle_up = lms.landmark[12].y < lms.landmark[10].y
    ring_up = lms.landmark[16].y < lms.landmark[14].y
    pinky_up = lms.landmark[20].y < lms.landmark[18].y
    return index_up and middle_up and ring_up and pinky_up

def is_closed_fist_gesture(lms):
    index_down = lms.landmark[8].y > lms.landmark[6].y
    middle_down = lms.landmark[12].y > lms.landmark[10].y
    ring_down = lms.landmark[16].y > lms.landmark[14].y
    pinky_down = lms.landmark[20].y > lms.landmark[18].y
    return index_down and middle_down and ring_down and pinky_down

def is_pinch_gesture(lms):
    thumb_tip = lms.landmark[4]
    index_tip = lms.landmark[8]
    dist = math.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y)
    return dist < 0.04

def reset_auth():
    global auth_authenticated, auth_current_step, auth_failed_attempts, auth_time_left, auth_hard_locked, auth_active, auth_start_time, prev_hand_angle, accumulated_cw_rotation
    with auth_lock:
        if auth_hard_locked:
            auth_hard_locked = False
            auth_failed_attempts = 0
            log_auth_event("ADMIN: Security lock override. Resetting lockdown status.", "info")
            
        auth_authenticated = False
        auth_current_step = 0
        auth_time_left = 30.0
        auth_active = True
        auth_start_time = time.time()
        prev_hand_angle = None
        accumulated_cw_rotation = 0.0
        log_auth_event("AUTH: Challenge initiated. Perform gesture 1: Open Palm.", "info")

def get_auth_status():
    with auth_lock:
        return {
            "authenticated": auth_authenticated,
            "current_step": auth_current_step,
            "failed_attempts": auth_failed_attempts,
            "time_left": round(auth_time_left, 1),
            "hard_locked": auth_hard_locked,
            "auth_active": auth_active,
            "logs": list(auth_logs)
        }
