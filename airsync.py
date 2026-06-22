import cv2
import numpy as np
import pyautogui
import pydirectinput
import math
import pygame
import mediapipe as mp
import speech_recognition as sr
import threading
from flask import Flask, Response

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
cap = cv2.VideoCapture(0)

def generate_frames():
    global plocX_r, plocY_r, plocX_l, plocY_l, clicked, prev_angle, grabbing
    while True:
        success, img = cap.read()
        if not success: break
        img = cv2.flip(img, 1)
        h, w, _ = img.shape
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
            
            # Check for Command States
            r_fist = False
            if has_right:
                r_lms = hands_data["Right"]
                r_fist = r_lms.landmark[12].y > r_lms.landmark[10].y and r_lms.landmark[16].y > r_lms.landmark[14].y
            
            l_fist = False
            if has_left:
                l_lms = hands_data["Left"]
                l_fist = l_lms.landmark[12].y > l_lms.landmark[10].y and l_lms.landmark[16].y > l_lms.landmark[14].y

            # --- NAVIGATION GATING LOGIC ---
            # Mouse should NOT move if a fist (Right for Dial, Left for Grab) is active
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
                    print(f"[Left Mouse Move] Target: ({int(clocX_l)}, {int(clocY_l)}) | Raw index: ({l_idx.x:.2f}, {l_idx.y:.2f})")
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
                
                mp_draw.draw_landmarks(img, l_lms, mp_hands.HAND_CONNECTIONS)

            # --- RIGHT HAND LOGIC ---
            if has_right:
                r_lms = hands_data["Right"]
                wrist, r_idx, thumb = r_lms.landmark[0], r_lms.landmark[8], r_lms.landmark[4]

                # Right Hand Navigation (only if Left hand isn't present or grabbing)
                if not has_left and should_move:
                    tx_r = np.interp(r_idx.x * w, (frame_r, w - frame_r), (0, sw))
                    ty_r = np.interp(r_idx.y * h, (frame_r, h - frame_r), (0, sh))
                    clocX_r = plocX_r + (tx_r - plocX_r) / smooth_val_r
                    clocY_r = plocY_r + (ty_r - plocY_r) / smooth_val_r
                    print(f"[Right Mouse Move] Target: ({int(clocX_r)}, {int(clocY_r)}) | Raw index: ({r_idx.x:.2f}, {r_idx.y:.2f})")
                    pydirectinput.moveTo(int(clocX_r), int(clocY_r))
                    plocX_r, plocY_r = clocX_r, clocY_r

                # Rotary Logic (Navigation is blocked while r_fist is True)
                if r_fist:
                    curr_angle = math.degrees(math.atan2(r_idx.y - wrist.y, r_idx.x - wrist.x))
                    if prev_angle is not None:
                        diff = curr_angle - prev_angle
                        if abs(diff) < 45: 
                            pyautogui.scroll(int(diff * 9)) # Increased sensitivity for smoother dials
                    prev_angle = curr_angle
                    cv2.putText(img, "ROTARY LOCK - MOUSE FROZEN", (20, 50), 1, 1.5, (255, 0, 255), 2)
                else:
                    prev_angle = None
                    # Click Logic
                    click_dist = math.hypot(r_idx.x - thumb.x, r_idx.y - thumb.y)
                    if click_dist < 0.04 and not clicked:
                        pydirectinput.click()
                        play_ui_tone(1100)
                        clicked = True
                    elif click_dist > 0.05: clicked = False
                
                mp_draw.draw_landmarks(img, r_lms, mp_hands.HAND_CONNECTIONS)

        cv2.putText(img, f"VOICE: {latest_text}", (20, h-20), 1, 1.2, (0, 255, 0), 2)
        ret, buffer = cv2.imencode('.jpg', img)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)