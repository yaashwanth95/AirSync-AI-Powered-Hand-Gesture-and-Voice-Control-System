import cv2
import numpy as np
import time
import threading
from modules.audio import play_ui_tone

camera_active = False
camera_error = None
camera_lock = threading.Lock()
cap = None

def _open_camera():
    global camera_error
    # Probe index 0 first, then 1-4
    for idx in range(5):
        for backend in [None, cv2.CAP_DSHOW, cv2.CAP_MSMF]:
            try:
                if backend is not None:
                    c = cv2.VideoCapture(idx, backend)
                else:
                    c = cv2.VideoCapture(idx)
                
                if c.isOpened():
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    print(f"INFO: Camera successfully opened on index {idx} with backend {backend}.")
                    return c
            except Exception as e:
                print(f"WARNING: Exception probing camera index {idx} (backend {backend}): {e}")
    camera_error = "Camera Unavailable"
    return None

def create_placeholder_frame(text="Camera Offline"):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.0
    color = (68, 34, 255) if "Unavailable" in text or "disconnected" in text else (128, 128, 128)
    thickness = 2
    
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (640 - text_size[0]) // 2
    text_y = (480 + text_size[1]) // 2
    
    cv2.putText(img, text, (text_x, text_y), font, font_scale, color, thickness)
    cv2.rectangle(img, (10, 10), (630, 470), color, 1)
    
    ret, buffer = cv2.imencode('.jpg', img)
    return buffer.tobytes()

def start_camera():
    global camera_active, cap, camera_error
    with camera_lock:
        if camera_active and cap is not None:
            return {"status": "success", "message": "Camera already running"}
        camera_error = None
        c = _open_camera()
        if c is not None:
            cap = c
            camera_active = True
            return {"status": "success", "message": "Camera started successfully"}
        else:
            camera_active = False
            return {"status": "error", "message": camera_error or "Camera Unavailable"}

def stop_camera():
    global camera_active, cap
    with camera_lock:
        camera_active = False
        if cap is not None:
            try:
                cap.release()
            except Exception as e:
                print(f"Error releasing camera: {e}")
            cap = None
    return {"status": "success", "message": "Camera stopped successfully"}

def generate_frames(auth_module, gesture_module, voice_module):
    global cap, camera_active, camera_error
    last_camera_active = False
    failed_frame_count = 0

    while True:
        with camera_lock:
            active = camera_active
            camera_obj = cap
            err = camera_error

        if not active or camera_obj is None:
            msg = err if err else "Camera Offline"
            frame_bytes = create_placeholder_frame(msg)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)
            last_camera_active = False
            failed_frame_count = 0
            continue

        if not last_camera_active:
            last_camera_active = True
            failed_frame_count = 0

        try:
            success, img = camera_obj.read()
        except Exception:
            success = False
            img = None

        if not success or img is None:
            failed_frame_count += 1
            if failed_frame_count > 20:  # Only disconnect after 20 consecutive failures
                with camera_lock:
                    camera_error = "Camera disconnected"
                    camera_active = False
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                        cap = None
            time.sleep(0.03)
            continue
        else:
            failed_frame_count = 0

        img = cv2.flip(img, 1)
        h, w, _ = img.shape

        # Timer countdown check
        if auth_module.auth_active and not auth_module.auth_authenticated and not auth_module.auth_hard_locked:
            elapsed = time.time() - auth_module.auth_start_time
            auth_module.auth_time_left = max(0.0, 30.0 - elapsed)
            if auth_module.auth_time_left <= 0.0:
                with auth_module.auth_lock:
                    auth_module.auth_failed_attempts += 1
                    auth_module.log_auth_event(f"TIMEOUT - 30 seconds expired. Attempt {auth_module.auth_failed_attempts}/3.", "warn")
                    auth_module.auth_current_step = 0
                    auth_module.auth_active = False
                    auth_module.prev_hand_angle = None
                    auth_module.accumulated_cw_rotation = 0.0
                    if auth_module.auth_failed_attempts >= 3:
                        auth_module.auth_hard_locked = True
                        auth_module.log_auth_event("ACCESS DENIED - System entered HARD LOCKDOWN.", "error")
                play_ui_tone(300)

        # Process gestures and overlay controls
        img = gesture_module.process_gestures_and_control(img, auth_module)

        # Draw Futuristic Security Gating overlay HUD
        if auth_module.auth_active and not auth_module.auth_authenticated and not auth_module.auth_hard_locked:
            cv2.rectangle(img, (10, 10), (340, 110), (10, 14, 20), -1)
            cv2.rectangle(img, (10, 10), (340, 110), (0, 170, 255), 1)
            cv2.putText(img, "SECURITY GATING: LOCKED", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            steps_desc = ["1. OPEN PALM", "2. CLOSED FIST", "3. ROTATE CW", "4. PINCH"]
            current_desc = steps_desc[auth_module.auth_current_step] if auth_module.auth_current_step < 4 else "UNLOCKED"
            cv2.putText(img, f"CHALLENGE: {current_desc}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 170, 255), 1)
            cv2.putText(img, f"TIME LEFT: {auth_module.auth_time_left:.1f}s", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        elif auth_module.auth_hard_locked:
            cv2.rectangle(img, (10, 10), (340, 90), (10, 14, 20), -1)
            cv2.rectangle(img, (10, 10), (340, 90), (0, 0, 255), 2)
            cv2.putText(img, "SYSTEM LOCKED DOWN", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(img, "3 FAILURES. CALL ADMIN.", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        elif auth_module.auth_authenticated:
            cv2.putText(img, "SECURE OPERATOR MONITOR ACTIVE", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 136), 1)

        cv2.putText(img, f"VOICE: {voice_module.latest_text}", (20, h-20), 1, 1.2, (0, 255, 0), 2)
        ret, buffer = cv2.imencode('.jpg', img)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
