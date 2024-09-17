import os
from datetime import datetime
import numpy as np
import cv2
import urllib.request


def read_image(url):
    req = urllib.request.urlopen(url)
    arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
    frame = cv2.imdecode(arr, -1)
    return frame


url = 'http://192.168.123.122:2000/image?source=video_capture&id=0'
frame = read_image(url)
wh = frame.shape[1::-1]
print(f"wh = {wh}")

path = 'VDO'
os.makedirs(path, exist_ok=True)
vidos_name = os.path.join(path, datetime.now().strftime("%y%m%d-%H%M%S.mp4"))

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(vidos_name, fourcc, 5.0, wh)

while True:
    frame = read_image(url)
    out.write(frame)
    cv2.imshow('Recording', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

out.release()
cv2.destroyAllWindows()
