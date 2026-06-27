import speech_recognition as sr
import threading

voice_running = False
voice_error = None
voice_logs = []
voice_lock = threading.Lock()
voice_thread = None
latest_text = "Stabilized Control Active"

recognizer = sr.Recognizer()

def voice_listener():
    global latest_text, voice_running, voice_error, voice_logs
    
    try:
        with sr.Microphone() as source:
            pass
    except Exception as e:
        with voice_lock:
            voice_error = "Microphone unavailable"
            voice_running = False
        latest_text = "Mic Unavailable"
        return

    while True:
        with voice_lock:
            if not voice_running:
                break
        
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=2.0, phrase_time_limit=3)
                
                with voice_lock:
                    if not voice_running:
                        break
                
                text = recognizer.recognize_google(audio)
                if text:
                    latest_text = f"Recognized: {text}"
                    with voice_lock:
                        voice_logs.append(f"Recognized: {text}")
                        if len(voice_logs) > 50:
                            voice_logs.pop(0)
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            with voice_lock:
                voice_error = "Speech service error"
        except Exception as e:
            with voice_lock:
                voice_error = f"Voice error: {str(e)}"
                voice_running = False
            break

def start_voice():
    global voice_running, voice_thread, voice_error, latest_text
    with voice_lock:
        if voice_running:
            return {"status": "success", "message": "Voice already running"}
        voice_error = None
        voice_running = True
        latest_text = "Listening..."
        voice_thread = threading.Thread(target=voice_listener, daemon=True)
        voice_thread.start()
    return {"status": "success", "message": "Voice started successfully"}

def stop_voice():
    global voice_running, latest_text
    with voice_lock:
        voice_running = False
    latest_text = "OFF"
    return {"status": "success", "message": "Voice stopped successfully"}
