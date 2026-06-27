import cv2
import numpy as np
import pyautogui
import pydirectinput
import math
import mediapipe as mp
from modules.audio import play_ui_tone

# Safety settings
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0
sw, sh = pyautogui.size()

# Sensitivity
frame_r = 140
smooth_val_r = 5  
smooth_val_l = 10 

plocX_r, plocY_r = 0, 0
plocX_l, plocY_l = 0, 0
clicked, grabbing = False, False
prev_angle = None

# MediaPipe Detector
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

detector = None
mediapipe_error = None
try:
    detector = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.8, min_tracking_confidence=0.8)
except Exception as e:
    mediapipe_error = f"MediaPipe initialization failure: {str(e)}"
    print(mediapipe_error)

def process_gestures_and_control(img, auth_module):
    global plocX_r, plocY_r, plocX_l, plocY_l, clicked, prev_angle, grabbing
    
    h, w, _ = img.shape
    results = None
    
    if detector is not None:
        try:
            results = detector.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        except Exception as e:
            print(f"MediaPipe process error: {e}")

    if results and results.multi_hand_landmarks and results.multi_handedness:
        hands_data = {}
        for i, res in enumerate(results.multi_handedness):
            if i < len(results.multi_hand_landmarks):
                label = res.classification[0].label 
                hands_data[label] = results.multi_hand_landmarks[i]

        has_left = "Left" in hands_data
        has_right = "Right" in hands_data
        
        auth_hand_lms = None
        if has_right:
            auth_hand_lms = hands_data["Right"]
        elif has_left:
            auth_hand_lms = hands_data["Left"]

        # Authentication Sequence Gating
        if auth_module.auth_active and not auth_module.auth_authenticated and not auth_module.auth_hard_locked and auth_hand_lms:
            if auth_module.auth_current_step == 0:
                if auth_module.is_open_palm_gesture(auth_hand_lms):
                    with auth_module.auth_lock:
                        auth_module.auth_current_step = 1
                        auth_module.log_auth_event("AUTH: Open Palm detected. Step 1/4 Complete. Perform Closed Fist.", "info")
                    play_ui_tone(800)
            elif auth_module.auth_current_step == 1:
                if auth_module.is_closed_fist_gesture(auth_hand_lms):
                    with auth_module.auth_lock:
                        auth_module.auth_current_step = 2
                        auth_module.accumulated_cw_rotation = 0.0
                        auth_module.prev_hand_angle = None
                        auth_module.log_auth_event("AUTH: Closed Fist detected. Step 2/4 Complete. Rotate hand clockwise.", "info")
                    play_ui_tone(900)
            elif auth_module.auth_current_step == 2:
                wrist = auth_hand_lms.landmark[0]
                mcp = auth_hand_lms.landmark[9]
                curr_angle = math.degrees(math.atan2(mcp.y - wrist.y, mcp.x - wrist.x))
                if auth_module.prev_hand_angle is not None:
                    diff = curr_angle - auth_module.prev_hand_angle
                    if diff < -180: diff += 360
                    elif diff > 180: diff -= 360
                    if diff > 0.5:
                        auth_module.accumulated_cw_rotation += diff
                auth_module.prev_hand_angle = curr_angle
                
                if auth_module.accumulated_cw_rotation >= 60.0:
                    with auth_module.auth_lock:
                        auth_module.auth_current_step = 3
                        auth_module.log_auth_event("AUTH: Clockwise Rotation detected. Step 3/4 Complete. Perform Pinch.", "info")
                    play_ui_tone(1000)
            elif auth_module.auth_current_step == 3:
                if auth_module.is_pinch_gesture(auth_hand_lms):
                    with auth_module.auth_lock:
                        auth_module.auth_current_step = 4
                        auth_module.auth_authenticated = True
                        auth_module.auth_active = False
                        auth_module.log_auth_event("ACCESS GRANTED - Operator Authenticated. All controls active.", "success")
                    play_ui_tone(1100)

        # OS Navigation Controls (Gated by Authentication)
        if auth_module.auth_authenticated:
            r_fist = False
            if has_right:
                r_lms = hands_data["Right"]
                r_fist = r_lms.landmark[12].y > r_lms.landmark[10].y and r_lms.landmark[16].y > r_lms.landmark[14].y
            
            l_fist = False
            if has_left:
                l_lms = hands_data["Left"]
                l_fist = l_lms.landmark[12].y > l_lms.landmark[10].y and l_lms.landmark[16].y > l_lms.landmark[14].y

            should_move = not r_fist and not l_fist

            # Left hand control
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

            # Right hand control
            if has_right:
                r_lms = hands_data["Right"]
                wrist_pt, r_idx, thumb = r_lms.landmark[0], r_lms.landmark[8], r_lms.landmark[4]

                if not has_left and should_move:
                    tx_r = np.interp(r_idx.x * w, (frame_r, w - frame_r), (0, sw))
                    ty_r = np.interp(r_idx.y * h, (frame_r, h - frame_r), (0, sh))
                    clocX_r = plocX_r + (tx_r - plocX_r) / smooth_val_r
                    clocY_r = plocY_r + (ty_r - plocY_r) / smooth_val_r
                    pydirectinput.moveTo(int(clocX_r), int(clocY_r))
                    plocX_r, plocY_r = clocX_r, clocY_r

                if r_fist:
                    curr_angle = math.degrees(math.atan2(r_idx.y - wrist_pt.y, r_idx.x - wrist_pt.x))
                    if prev_angle is not None:
                        diff = curr_angle - prev_angle
                        if abs(diff) < 45: 
                            pyautogui.scroll(int(diff * 9))
                    prev_angle = curr_angle
                    cv2.putText(img, "ROTARY LOCK - MOUSE FROZEN", (20, 150), 1, 1.2, (255, 0, 255), 2)
                else:
                    prev_angle = None
                    click_dist = math.hypot(r_idx.x - thumb.x, r_idx.y - thumb.y)
                    if click_dist < 0.04 and not clicked:
                        pydirectinput.click()
                        play_ui_tone(1100)
                        clicked = True
                    elif click_dist > 0.05: clicked = False

        # Draw Landmarks
        if has_left:
            mp_draw.draw_landmarks(img, hands_data["Left"], mp_hands.HAND_CONNECTIONS)
        if has_right:
            mp_draw.draw_landmarks(img, hands_data["Right"], mp_hands.HAND_CONNECTIONS)

    return img
