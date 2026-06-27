from flask import Flask, Response, jsonify, request
from modules import audio, auth, voice, copilot, gesture, camera

app = Flask(__name__)

@app.route('/')
def index():
    try:
        with open("nuclear_reactor Control Panel.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading control panel: {e}", 500

@app.route('/video_feed')
def video_feed():
    return Response(camera.generate_frames(auth, gesture, voice), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/auth_status')
def auth_status_api():
    return jsonify(auth.get_auth_status())

@app.route('/api/auth_reset', methods=['POST'])
def auth_reset():
    auth.reset_auth()
    return jsonify({"status": "success"})

@app.route('/api/copilot', methods=['POST'])
def copilot_api():
    data = request.json or {}
    result = copilot.analyze_telemetry(data)
    return jsonify(result)

@app.route('/api/camera/start', methods=['POST'])
def api_camera_start():
    res = camera.start_camera()
    status_code = 200 if res["status"] == "success" else 500
    return jsonify(res), status_code

@app.route('/api/camera/stop', methods=['POST'])
def api_camera_stop():
    res = camera.stop_camera()
    return jsonify(res)

@app.route('/api/voice/start', methods=['POST'])
def api_voice_start():
    res = voice.start_voice()
    return jsonify(res)

@app.route('/api/voice/stop', methods=['POST'])
def api_voice_stop():
    res = voice.stop_voice()
    return jsonify(res)

@app.route('/api/system_status')
def api_system_status():
    with camera.camera_lock:
        cam_active = camera.camera_active
        cam_err = camera.camera_error
    with voice.voice_lock:
        v_running = voice.voice_running
        v_err = voice.voice_error
        v_logs = list(voice.voice_logs)
    
    return jsonify({
        "camera_active": cam_active,
        "camera_error": cam_err,
        "voice_running": v_running,
        "voice_error": v_err,
        "voice_logs": v_logs,
        "gesture_active": cam_active and gesture.detector is not None and not auth.auth_hard_locked
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)