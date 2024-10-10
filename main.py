import multiprocessing
import time
import numpy as np
from flask import Flask, render_template, Response, request, redirect, url_for
import socket
import cv2
from datetime import datetime
from hexss import json_load, json_update
import platform

# Conditional imports based on the platform
if platform.system() == "Windows":
    import mss


def display_capture(data):
    if platform.system() == "Windows":
        with mss.mss() as sct:
            while True:
                screenshot = sct.grab(sct.monitors[0])
                image = np.array(screenshot)
                data['display_capture'] = image


def video_capture(data, camera_id):
    def setup():
        cap = cv2.VideoCapture(int(camera_id))
        if data.get(camera_id) and data[camera_id].get('wight') and data[camera_id].get('height'):
            cap.set(3, data[camera_id]['wight'])
            cap.set(4, data[camera_id]['height'])
        return cap

    cap = setup()
    while True:
        if data[f'camera_{camera_id}_enabled']:
            status, img = cap.read()
            data[f'status_{camera_id}'] = status
            if status:
                data[f'img_{camera_id}'] = img.copy()
            else:
                time.sleep(1)
                cap = setup()
        else:
            data[f'status_{camera_id}'] = False
            data[f'img_{camera_id}'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)


def get_data(data, source, camera_id):
    if source == 'display_capture':
        frame = data['display_capture']
    elif source == 'video_capture':
        frame = data[f'img_{camera_id}']
        success = data[f'status_{camera_id}']
        if not success:
            cv2.putText(frame, f'Failed to capture image', (30, 50), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, f'from camera {camera_id}', (30, 90), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (30, 130), 1, 2, (0, 0, 255), 2)

    ret, buffer = cv2.imencode('.jpg', frame)
    # encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]  # Adjust quality (0-100)
    # ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


app = Flask(__name__)


@app.route('/')
def index():
    camera_states = {
        f'camera_{i}': app.config['data'][f'camera_{i}_enabled']
        for i in range(app.config['data']['number_of_cameras'])
    }
    return render_template('index.html', camera_states=camera_states)


@app.route('/update_cameras', methods=['POST'])
def update_cameras():
    for i in range(app.config['data']['number_of_cameras']):
        camera_key = f'camera_{i}'
        app.config['data'][f'{camera_key}_enabled'] = camera_key in request.form
    return redirect(url_for('index'))


def _get_image(data, source, camera_id):
    buffer = get_data(data, source, camera_id)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    return _get_image(app.config['data'], source, camera_id)


def _get_video(data, source, camera_id):
    while True:
        buffer = get_data(data, source, camera_id)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video')
def get_video():
    source = request.args.get('source', default='display_capture', type=str)
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    return Response(
        _get_video(app.config['data'], source, camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data):
    import logging
    log = logging.getLogger('werkzeug')
    log.disabled = True

    app.config['data'] = data
    ipv4_address = data['ipv4_address']
    print(f" * Running on http://{ipv4_address}:2000")
    app.run(host=ipv4_address, port=2000, debug=True, use_reloader=False)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    manager = multiprocessing.Manager()
    data = manager.dict()
    config = json_load('config.json', {
        "ipv4_address": "auto",
        "number_of_cameras": 1,
        "0": {
            "wight": 640,
            "height": 480,
        },
        "1": {
            "wight": 640,
            "height": 480,
        }
    })
    for k, v in config.items():
        data[k] = v

    if data['ipv4_address'] == 'auto':
        hostname = socket.gethostname()
        data['ipv4_address'] = socket.gethostbyname(hostname)

    data['number_of_cameras'] = int(data['number_of_cameras'])
    print(data)

    for camera_id in range(data['number_of_cameras']):
        data[f'status_{camera_id}'] = False
        data[f'img_{camera_id}'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
        data[f'camera_{camera_id}_enabled'] = True  # Default to enabled
    data['display_capture'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)

    video_capture_process = [
        multiprocessing.Process(target=video_capture, args=(data, f'{camera_id}'))
        for camera_id in range(data['number_of_cameras'])
    ]
    display_capture_process = multiprocessing.Process(target=display_capture, args=(data,))
    run_server_process = multiprocessing.Process(target=run_server, args=(data,))

    # Start all processes
    for process in video_capture_process:
        process.start()
    display_capture_process.start()
    run_server_process.start()

    # Join all processes
    for process in video_capture_process:
        process.join()
    display_capture_process.join()
    run_server_process.join()
