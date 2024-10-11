import multiprocessing
import time
import numpy as np
from flask import Flask, render_template, Response, request, redirect, url_for
import socket
import cv2
from datetime import datetime
from hexss import json_load, json_update, dict_to_manager_dict
import platform
import logging
from typing import Dict, Any

# Conditional imports based on the platform
if platform.system() == "Windows":
    import mss


def display_capture(data: Dict[str, Any]) -> None:
    if platform.system() == "Windows":
        with mss.mss() as sct:
            while True:
                screenshot = sct.grab(sct.monitors[0])
                image = np.array(screenshot)
                data['display_capture'] = image


def video_capture(data: Dict[str, Any], camera_id: int) -> None:
    def setup():
        cap = cv2.VideoCapture(camera_id)
        if data['camera'][camera_id].get('width') and data['camera'][camera_id].get('height'):
            cap.set(3, data['camera'][camera_id]['width'])
            cap.set(4, data['camera'][camera_id]['height'])
        return cap

    cap = setup()
    while True:
        if data['camera'][camera_id]['setup']:
            data['camera'][camera_id]['setup'] = False
            cap = setup()

        if data['camera'][camera_id]['camera_enabled']:
            status, img = cap.read()
            data['camera'][camera_id]['status'] = status
            if status:
                data['camera'][camera_id]['img'] = img.copy()
            else:
                time.sleep(1)
                cap = setup()
        else:
            data['camera'][camera_id]['status'] = False
            data['camera'][camera_id]['img'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)


def get_data(data: Dict[str, Any], source: str, camera_id: int) -> np.ndarray:
    if source == 'video_capture':
        frame = data['camera'][camera_id]['img']
        status = data['camera'][camera_id]['status']
        if not status:
            frame = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
            cv2.putText(frame, f'Failed to capture image', (30, 50), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, f'from camera {camera_id}', (30, 90), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (30, 130), 1, 2, (0, 0, 255), 2)
    else:  # source == 'display_capture':
        frame = data['display_capture']

    ret, buffer = cv2.imencode('.jpg', frame)
    # encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]  # Adjust quality (0-100)
    # ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


app = Flask(__name__)


@app.route('/')
def index():
    data = app.config['data']
    camera_states = {
        f'camera_{camera_id}': data['camera'][camera_id]['camera_enabled']
        for camera_id in range(len(data['camera']))
    }
    return render_template('index.html', camera_states=camera_states)


@app.route('/update_cameras', methods=['POST'])
def update_cameras():
    global config

    data = app.config['data']
    for camera_id in range(len(data['camera'])):
        camera_key = f'camera_{camera_id}'
        data['camera'][camera_id]['camera_enabled'] = camera_key in request.form
        width = request.form.get(f'w{camera_key}')
        height = request.form.get(f'h{camera_key}')
        if width and height:
            data['camera'][camera_id]['width'] = int(width)
            data['camera'][camera_id]['height'] = int(height)
            data['camera'][camera_id]['setup'] = True

            # update config file
            config = json_load('config.json')
            config['camera'][camera_id]['width'] = int(width)
            config['camera'][camera_id]['height'] = int(height)
            json_update('config.json', config)

    return redirect(url_for('index'))


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    buffer = get_data(app.config['data'], source, camera_id)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/video')
def get_video():
    source = request.args.get('source', default='display_capture', type=str)
    camera_id = request.args.get('id', default=0, type=int)

    def generate():
        while True:
            buffer = get_data(app.config['data'], source, camera_id)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data: Dict[str, Any]) -> None:
    log = logging.getLogger('werkzeug')
    log.disabled = True
    app.config['data'] = data
    ipv4_address = data['ipv4_address']
    print(f" * Running on http://{ipv4_address}:2000")
    app.run(host=ipv4_address, port=2000, debug=False, use_reloader=False)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    manager = multiprocessing.Manager()
    config = json_load('config.json', {
        "ipv4_address": "auto",
        "camera": [
            {
                "width": 640,
                "height": 480,
            },
            {
                "width": 640,
                "height": 480,
            }
        ]
    })
    json_update('config.json', config)
    data = dict_to_manager_dict(manager, config)
    if data['ipv4_address'] == 'auto':
        hostname = socket.gethostname()
        data['ipv4_address'] = socket.gethostbyname(hostname)

    for camera_id in range(len(data['camera'])):
        data['camera'][camera_id]['status'] = False
        data['camera'][camera_id]['img'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
        data['camera'][camera_id]['camera_enabled'] = True  # Default to enabled
        data['camera'][camera_id]['setup'] = False
    data['display_capture'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)

    processes = [
        multiprocessing.Process(target=video_capture, args=(data, camera_id))
        for camera_id in range(len(data['camera']))
    ]
    processes.append(multiprocessing.Process(target=display_capture, args=(data,)))
    processes.append(multiprocessing.Process(target=run_server, args=(data,)))

    for process in processes:
        process.start()

    for process in processes:
        process.join()
