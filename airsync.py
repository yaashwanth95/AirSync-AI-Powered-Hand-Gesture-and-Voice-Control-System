import cv2
import numpy as np
import pyautogui
import pydirectinput
import math
import pygame
import mediapipe as mp
import speech_recognition as sr
import threading
import time
import os
import datetime
from flask import Flask, Response, jsonify, request

# --- 1. CORE SYSTEM CONFIG ---
app = Flask(__name__)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0
sw, sh = pyautogui.size()

# Sensitivity Settings
frame_r = 140
smooth_val_r = 5  
smooth_val_l = 10 

plocX_r, plocY_r = 0, 0
plocX_l, plocY_l = 0, 0
clicked, grabbing = False, False
prev_angle = None
latest_text = "Stabilized Control Active"

# --- AUTHENTICATION STATE & LOGGING ---
auth_authenticated = False
auth_current_step = 0  # 0: Open Palm, 1: Closed Fist, 2: CW Rotation, 3: Pinch, 4: Authenticated
auth_failed_attempts = 0
auth_time_left = 30.0
auth_hard_locked = False
auth_active = False
auth_start_time = 0.0
auth_logs = ["Challenge waiting to start..."]
auth_lock = threading.Lock()

# CW Rotation Tracking Variables
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
    
    # Write to logs/auth_logs.txt
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "auth_logs.txt")
        with open(log_path, "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] [{status.upper()}] {msg}\n")
    except Exception as e:
        print(f"Error writing to auth log file: {e}")

# Gesture Helpers
def is_open_palm_gesture(lms):
    # Check that 4 fingers (Index, Middle, Ring, Pinky) are extended
    index_up = lms.landmark[8].y < lms.landmark[6].y
    middle_up = lms.landmark[12].y < lms.landmark[10].y
    ring_up = lms.landmark[16].y < lms.landmark[14].y
    pinky_up = lms.landmark[20].y < lms.landmark[18].y
    return index_up and middle_up and ring_up and pinky_up

def is_closed_fist_gesture(lms):
    # Check that 4 fingers are folded down below their pips
    index_down = lms.landmark[8].y > lms.landmark[6].y
    middle_down = lms.landmark[12].y > lms.landmark[10].y
    ring_down = lms.landmark[16].y > lms.landmark[14].y
    pinky_down = lms.landmark[20].y > lms.landmark[18].y
    return index_down and middle_down and ring_down and pinky_down

def is_pinch_gesture(lms):
    # Pinch between thumb tip (4) and index tip (8)
    thumb_tip = lms.landmark[4]
    index_tip = lms.landmark[8]
    dist = math.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y)
    return dist < 0.04

# Audio Engine
pygame.mixer.init()
def play_ui_tone(freq):
    duration = 0.08
    t = np.linspace(0, duration, int(44100 * duration), False)
    wave = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    pygame.sndarray.make_sound(np.stack((wave, wave), axis=-1)).play()

# --- 2. PACED VOICE ENGINE ---
recognizer = sr.Recognizer()
def voice_listener():
    global latest_text
    while True:
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, phrase_time_limit=3)
                text = recognizer.recognize_google(audio)
                words = text.split()
                chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
                for chunk in chunks:
                    pyautogui.write(chunk + " ")
                    latest_text = f"Logged: {chunk}"
                    threading.Event().wait(0.3) 
        except:
            latest_text = "Listening..."

threading.Thread(target=voice_listener, daemon=True).start()

# --- 3. VISION & STABILIZED PRIORITY ENGINE ---
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
detector = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.8, min_tracking_confidence=0.8)

# Robust Camera Initialization with fallback search (non-blocking — warm-up happens in generate_frames)
def _open_camera():
    for idx in [0, 1, 2]:
        c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW = Windows DirectShow, avoids blank startup
        if c.isOpened():
            c.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            c.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"INFO: Camera opened on index {idx}. Will warm up inside frame loop.")
            return c
        print(f"WARNING: Camera index {idx} failed to open.")
    print("ERROR: No camera could be initialized on index 0, 1, or 2.")
    return cv2.VideoCapture(0)

cap = _open_camera()

def generate_frames():
    global plocX_r, plocY_r, plocX_l, plocY_l, clicked, prev_angle, grabbing
    global auth_active, auth_current_step, auth_time_left, auth_authenticated, auth_failed_attempts, auth_hard_locked, auth_start_time
    global prev_hand_angle, accumulated_cw_rotation

    # Inline warm-up: discard the first N frames that Windows cameras produce as black
    warmup_frames_remaining = 30

    while True:
        success, img = cap.read()
        if not success or img is None:
            # Don't break — a single dropped frame should not kill the stream
            time.sleep(0.02)
            continue

        # Skip early black frames during camera warm-up
        if warmup_frames_remaining > 0:
            warmup_frames_remaining -= 1
            continue

        img = cv2.flip(img, 1)
        h, w, _ = img.shape

        # Timer countdown check
        if auth_active and not auth_authenticated and not auth_hard_locked:
            elapsed = time.time() - auth_start_time
            auth_time_left = max(0.0, 30.0 - elapsed)
            if auth_time_left <= 0.0:
                with auth_lock:
                    auth_failed_attempts += 1
                    log_auth_event(f"TIMEOUT - 30 seconds expired. Attempt {auth_failed_attempts}/3.", "warn")
                    auth_current_step = 0
                    auth_active = False
                    prev_hand_angle = None
                    accumulated_cw_rotation = 0.0
                    if auth_failed_attempts >= 3:
                        auth_hard_locked = True
                        log_auth_event("ACCESS DENIED - System entered HARD LOCKDOWN.", "error")
                play_ui_tone(300)

        results = detector.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        if results.multi_hand_landmarks and results.multi_handedness:
            hands_data = {}
            for i, res in enumerate(results.multi_handedness):
                if i < len(results.multi_hand_landmarks):
                    label = res.classification[0].label 
                    hands_data[label] = results.multi_hand_landmarks[i]

            # Determine State
            has_left = "Left" in hands_data
            has_right = "Right" in hands_data
            
            # Select hand for authentication
            auth_hand_lms = None
            if has_right:
                auth_hand_lms = hands_data["Right"]
            elif has_left:
                auth_hand_lms = hands_data["Left"]

            # Active Authentication Sequence Gating
            if auth_active and not auth_authenticated and not auth_hard_locked and auth_hand_lms:
                if auth_current_step == 0:
                    if is_open_palm_gesture(auth_hand_lms):
                        with auth_lock:
                            auth_current_step = 1
                            log_auth_event("AUTH: Open Palm detected. Step 1/4 Complete. Perform Closed Fist.", "info")
                        play_ui_tone(800)
                elif auth_current_step == 1:
                    if is_closed_fist_gesture(auth_hand_lms):
                        with auth_lock:
                            auth_current_step = 2
                            accumulated_cw_rotation = 0.0
                            prev_hand_angle = None
                            log_auth_event("AUTH: Closed Fist detected. Step 2/4 Complete. Rotate hand clockwise.", "info")
                        play_ui_tone(900)
                elif auth_current_step == 2:
                    # Clockwise Rotation logic
                    wrist = auth_hand_lms.landmark[0]
                    mcp = auth_hand_lms.landmark[9]
                    curr_angle = math.degrees(math.atan2(mcp.y - wrist.y, mcp.x - wrist.x))
                    if prev_hand_angle is not None:
                        diff = curr_angle - prev_hand_angle
                        if diff < -180: diff += 360
                        elif diff > 180: diff -= 360
                        if diff > 0.5:
                            accumulated_cw_rotation += diff
                    prev_hand_angle = curr_angle
                    
                    if accumulated_cw_rotation >= 60.0:
                        with auth_lock:
                            auth_current_step = 3
                            log_auth_event("AUTH: Clockwise Rotation detected. Step 3/4 Complete. Perform Pinch.", "info")
                        play_ui_tone(1000)
                elif auth_current_step == 3:
                    if is_pinch_gesture(auth_hand_lms):
                        with auth_lock:
                            auth_current_step = 4
                            auth_authenticated = True
                            auth_active = False
                            log_auth_event("ACCESS GRANTED - Operator Authenticated. All controls active.", "success")
                        # Success chime: rapid rising tones
                        play_ui_tone(1100)
                        threading.Thread(target=lambda: (time.sleep(0.08), play_ui_tone(1300), time.sleep(0.08), play_ui_tone(1500))).start()

            # --- GATED COMMAND & NAVIGATION STATES (ONLY IF AUTHENTICATED) ---
            if auth_authenticated:
                r_fist = False
                if has_right:
                    r_lms = hands_data["Right"]
                    r_fist = r_lms.landmark[12].y > r_lms.landmark[10].y and r_lms.landmark[16].y > r_lms.landmark[14].y
                
                l_fist = False
                if has_left:
                    l_lms = hands_data["Left"]
                    l_fist = l_lms.landmark[12].y > l_lms.landmark[10].y and l_lms.landmark[16].y > l_lms.landmark[14].y

                should_move = not r_fist and not l_fist

                # --- LEFT HAND LOGIC ---
                if has_left:
                    l_lms = hands_data["Left"]
                    l_idx = l_lms.landmark[8]
                    
                    if should_move or grabbing:
                        tx_l = np.interp(l_idx.x * w, (frame_r, w - frame_r), (0, sw))
                        ty_l = np.interp(l_idx.y * h, (frame_r, h - frame_r), (0, sh))
                        clocX_l = plocX_l + (tx_l - plocX_l) / smooth_val_l
                        clocY_l = plocY_l + (ty_l - plocY_l) / smooth_val_l
                        pydirectinput.moveTo(int(clocX_l), int(clocY_l))
                        plocX_l, plocY_l = clocX_l, clocY_l

                    if l_fist and not grabbing:
                        pydirectinput.mouseDown()
                        grabbing = True
                        play_ui_tone(600)
                    elif not l_fist and grabbing:
                        pydirectinput.mouseUp()
                        grabbing = False
                        play_ui_tone(400)

                # --- RIGHT HAND LOGIC ---
                if has_right:
                    r_lms = hands_data["Right"]
                    wrist_pt, r_idx, thumb = r_lms.landmark[0], r_lms.landmark[8], r_lms.landmark[4]

                    # Right Hand Navigation (only if Left hand isn't present or grabbing)
                    if not has_left and should_move:
                        tx_r = np.interp(r_idx.x * w, (frame_r, w - frame_r), (0, sw))
                        ty_r = np.interp(r_idx.y * h, (frame_r, h - frame_r), (0, sh))
                        clocX_r = plocX_r + (tx_r - plocX_r) / smooth_val_r
                        clocY_r = plocY_r + (ty_r - plocY_r) / smooth_val_r
                        pydirectinput.moveTo(int(clocX_r), int(clocY_r))
                        plocX_r, plocY_r = clocX_r, clocY_r

                    # Rotary Logic (Navigation is blocked while r_fist is True)
                    if r_fist:
                        curr_angle = math.degrees(math.atan2(r_idx.y - wrist_pt.y, r_idx.x - wrist_pt.x))
                        if prev_angle is not None:
                            diff = curr_angle - prev_angle
                            if abs(diff) < 45: 
                                pyautogui.scroll(int(diff * 9)) # Increased sensitivity for smoother dials
                        prev_angle = curr_angle
                        cv2.putText(img, "ROTARY LOCK - MOUSE FROZEN", (20, 150), 1, 1.2, (255, 0, 255), 2)
                    else:
                        prev_angle = None
                        # Click Logic
                        click_dist = math.hypot(r_idx.x - thumb.x, r_idx.y - thumb.y)
                        if click_dist < 0.04 and not clicked:
                            pydirectinput.click()
                            play_ui_tone(1100)
                            clicked = True
                        elif click_dist > 0.05: clicked = False

            # Draw Hand Landmarks for alignment feedback
            if has_left:
                mp_draw.draw_landmarks(img, hands_data["Left"], mp_hands.HAND_CONNECTIONS)
            if has_right:
                mp_draw.draw_landmarks(img, hands_data["Right"], mp_hands.HAND_CONNECTIONS)

        # Draw Futuristic Security Gating overlay HUD
        if auth_active and not auth_authenticated and not auth_hard_locked:
            cv2.rectangle(img, (10, 10), (340, 110), (10, 14, 20), -1)
            cv2.rectangle(img, (10, 10), (340, 110), (0, 170, 255), 1)
            cv2.putText(img, "SECURITY GATING: LOCKED", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            steps_desc = ["1. OPEN PALM", "2. CLOSED FIST", "3. ROTATE CW", "4. PINCH"]
            current_desc = steps_desc[auth_current_step] if auth_current_step < 4 else "UNLOCKED"
            cv2.putText(img, f"CHALLENGE: {current_desc}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 170, 255), 1)
            cv2.putText(img, f"TIME LEFT: {auth_time_left:.1f}s", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        elif auth_hard_locked:
            cv2.rectangle(img, (10, 10), (340, 90), (10, 14, 20), -1)
            cv2.rectangle(img, (10, 10), (340, 90), (0, 0, 255), 2)
            cv2.putText(img, "SYSTEM LOCKED DOWN", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(img, "3 FAILURES. CALL ADMIN.", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        elif auth_authenticated:
            cv2.putText(img, "SECURE OPERATOR MONITOR ACTIVE", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 136), 1)

        cv2.putText(img, f"VOICE: {latest_text}", (20, h-20), 1, 1.2, (0, 255, 0), 2)
        ret, buffer = cv2.imencode('.jpg', img)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    try:
        # Load the control panel HTML and serve it
        with open("nuclear_reactor Control Panel.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading control panel: {e}", 500

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/auth_status')
def auth_status_api():
    with auth_lock:
        return jsonify({
            "authenticated": auth_authenticated,
            "current_step": auth_current_step,
            "failed_attempts": auth_failed_attempts,
            "time_left": round(auth_time_left, 1),
            "hard_locked": auth_hard_locked,
            "auth_active": auth_active,
            "logs": list(auth_logs)
        })

@app.route('/api/auth_reset', methods=['POST'])
def auth_reset():
    global auth_authenticated, auth_current_step, auth_failed_attempts, auth_time_left, auth_hard_locked, auth_active, auth_start_time, prev_hand_angle, accumulated_cw_rotation
    with auth_lock:
        if auth_hard_locked:
            # Administrative bypass/reset for testing & demo purposes
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
    return jsonify({"status": "success"})

@app.route('/api/copilot', methods=['POST'])
def copilot_api():
    data = request.json or {}
    
    # Extract telemetry
    core_temp = data.get("coolantTemp", 589)
    pressure = data.get("reactorCoolantPressure", 2235)
    flow = data.get("rcsFlow", 98.2)
    scram_active = data.get("scramActive", False)
    active_scenario = data.get("activeScenario", "")
    alarm_count = data.get("alarmCount", 0)
    
    # Calculate Digital Twin Health Score (0-100)
    health = 100
    
    if scram_active:
        health = 25
        status_desc = "EMERGENCY SHUTDOWN (SCRAM) IN PROGRESS"
        risk_level = "HIGH"
        risk_score = 75
        fail_prob = 10.0
        recommendations = [
            "• Monitor Core Subcooling Margin.",
            "• Verify all Control Rods are fully inserted (0%).",
            "• Maintain emergency boron injection if subcriticality margin is low."
        ]
        explanation = "Reactor SCRAM was manually or automatically initiated. Thermal power is decreasing rapidly, and rods are fully inserted. Decay heat must be managed via residual heat removal systems."
    else:
        # Penalties based on deviations
        temp_deviation = abs(core_temp - 589)
        if temp_deviation > 10:
            health -= int((temp_deviation - 10) * 1.5)
        
        press_deviation = abs(pressure - 2235)
        if press_deviation > 50:
            health -= int((press_deviation - 50) * 0.2)
            
        if flow < 95.0:
            health -= int((95.0 - flow) * 1.8)
            
        health -= alarm_count * 4
        
        if active_scenario:
            health -= 15
            
        health = max(0, min(100, health))
        
        # Risk assessment & predictions based on active scenario and health
        if health >= 90:
            risk_level = "LOW"
            risk_score = max(0, 100 - health)
            fail_prob = round((100 - health) * 0.1, 1)
            status_desc = "SYSTEMS IN NOMINAL STEADY STATE"
            recommendations = [
                "• Maintain steady state nominal power.",
                "• Continue standard logs and inspections."
            ]
            explanation = "All core thermodynamic and hydraulic parameters are within the green band. Control rod banks are at expected heights, and flow rate is stable."
        elif health >= 70:
            risk_level = "MEDIUM"
            risk_score = 100 - health
            fail_prob = round((100 - health) * 0.8, 1)
            
            # Custom status and recommendations based on scenario
            if "Pump" in active_scenario:
                status_desc = "DEGRADED CORE FLOW COMPROMISING HEAT TRANSFER"
                recommendations = [
                    "• Increase Loop 1 / Loop 2 Flow control knobs to compensate.",
                    "• Verify secondary primary coolant pump switch is enabled.",
                    "• Check coolant pump electrical bus voltages."
                ]
                explanation = f"Primary coolant pump failure has reduced loop flow rate to {flow}%. Core temperature is rising, and risk model indicates localized boiling possibility if flow is not restored."
            elif "Leak" in active_scenario:
                status_desc = "PRIMARY COOLANT DEPRESSURIZATION WARNING"
                recommendations = [
                    "• Engage Safety Injection system switches.",
                    "• Isolate primary loop leak path if possible.",
                    "• Monitor Pressurizer Level knob to verify margin."
                ]
                explanation = f"Primary loop pressure has dropped to {pressure} psia. A coolant leak is suspected. ECCS actuation is imminent if pressure falls below safety threshold."
            elif "Grid" in active_scenario:
                status_desc = "ELECTRICAL GRID FREQUENCY INSTABILITY"
                recommendations = [
                    "• Adjust Turbine Bypass valve setting to stabilize load.",
                    "• Trim control rod positions to manage thermal power output.",
                    "• Monitor generator frequency output."
                ]
                explanation = "Grid frequency is fluctuating wildly, causing turbine-generator load mismatches. Thermal power must be adjusted to prevent generator trip."
            else:
                status_desc = "SYSTEM STABILITY DEGRADED"
                recommendations = [
                    "• Reduce Power Setpoint to 80%.",
                    "• Verify control rod positions match thermal output.",
                    "• Check feedwater flow balance."
                ]
                explanation = f"Reactor health has decreased to {health}%. Temperature or pressure deviations are exceeding nominal limits. Operators should monitor core variables closely."
        else:
            risk_level = "HIGH"
            risk_score = 100 - health
            fail_prob = round((100 - health) * 1.2, 1)
            fail_prob = min(99.9, fail_prob)
            
            if "Runaway" in active_scenario:
                status_desc = "CRITICAL: THERMAL RUNAWAY IN CORE"
                recommendations = [
                    "• INITIATE MANUAL SCRAM IMMEDIATELY.",
                    "• Fully insert all control rod banks.",
                    "• Initiate emergency boration to maximum ppm."
                ]
                explanation = f"Core thermal runaway is in progress! Temperature has surged to {core_temp} deg F. Fuel centerline temperature is approaching safety limits. Immediate SCRAM required to prevent cladding damage."
            elif "Leak" in active_scenario:
                status_desc = "CRITICAL: LOCA (LOSS OF COOLANT ACCIDENT)"
                recommendations = [
                    "• Verify ECCS injection is at maximum flow.",
                    "• Execute emergency reactor SCRAM.",
                    "• Monitor containment pressure and trigger containment spray."
                ]
                explanation = f"Severe loss of coolant accident (LOCA). Coolant pressure is dangerously low at {pressure} psia. Emergency core cooling systems must be manually verified. Execute SCRAM immediately."
            elif "Spike" in active_scenario:
                status_desc = "CRITICAL: PRIMARY SYSTEM OVERPRESSURE"
                recommendations = [
                    "• Open Pressurizer Relief Valve.",
                    "• Engage Containment Spray system.",
                    "• Reduce power setpoint and insert rods."
                ]
                explanation = f"RCS Pressure has spiked dangerously to {pressure} psia. Relief valves must be opened to prevent structural integrity failure of the reactor vessel."
            else:
                status_desc = "CRITICAL LIMIT EXCEEDED"
                recommendations = [
                    "• Prepare for manual reactor SCRAM.",
                    "• Verify auxiliary feedwater pumps are running.",
                    "• Ensure control room alerts are acknowledged."
                ]
                explanation = f"Reactor parameters are critically out of range. Health score is at {health}%. Immediate intervention required to prevent automatic reactor trip."

    return jsonify({
        "health": health,
        "riskLevel": risk_level,
        "riskScore": risk_score,
        "failProbability": fail_prob,
        "statusDesc": status_desc,
        "recommendations": recommendations,
        "explanation": explanation
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)