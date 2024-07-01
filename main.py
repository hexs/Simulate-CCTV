import multiprocessing
import numpy as np
from flask import Flask, render_template, Response, request
import socket
import cv2
from PIL import ImageGrab, Image


def display_capture(data):
    while True:
        pil_image = ImageGrab.grab()
        image_bgr = np.array(pil_image)
        image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        data['display_capture'] = image


def video_capture(data):
    cap = cv2.VideoCapture(0)
    while True:
        status, img = cap.read()
        data['status'] = status
        if status:
            data['img'] = img.copy()
        else:
            cap = cv2.VideoCapture(0)


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


def _get_image(data, source):
    if source == 'display_capture':
        frame = data['display_capture']
    elif source == 'video_capture':
        frame = data['img']
        success = data['status']
        if not success:
            cv2.putText(frame, 'Failed to capture image', (50, 50), 1, 2, (0, 0, 255), 2)
    else:
        return 'error'
    ret, buffer = cv2.imencode('.jpg', frame)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    return _get_image(app.config['data'], source)


def _get_video(data, source):
    while True:
        if source == 'display_capture':
            frame = data['display_capture']
        elif source == 'video_capture':
            frame = data['img']
            success = data['status']
            if not success:
                cv2.putText(frame, 'Failed to capture image', (50, 50), 1, 2, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video')
def get_video():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    return Response(
        _get_video(app.config['data'], source),
        mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data):
    app.config['data'] = data
    hostname = socket.gethostname()
    ipv4_address = socket.gethostbyname(hostname)
    app.run(host=ipv4_address, port=2000, debug=True, use_reloader=False)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    manager = multiprocessing.Manager()
    data = manager.dict()
    data['status'] = False
    data['img'] = np.full((500, 500, 3), (50, 50, 50), dtype=np.uint8)
    data['display_capture'] = np.full((500, 500, 3), (50, 50, 50), dtype=np.uint8)

    video_capture_process = multiprocessing.Process(target=video_capture, args=(data,))
    display_capture_process = multiprocessing.Process(target=display_capture, args=(data,))
    run_server_process = multiprocessing.Process(target=run_server, args=(data,))

    video_capture_process.start()
    display_capture_process.start()
    run_server_process.start()

    video_capture_process.join()
    display_capture_process.join()
    run_server_process.join()
