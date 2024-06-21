import cv2
import urllib.request
import numpy as np


def get_from_image():
    url = 'http://192.168.225.137:2000/old-image'
    while True:
        req = urllib.request.urlopen(url)
        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        img = cv2.imdecode(arr, -1)

        cv2.imshow('Image from URL', img)
        cv2.waitKey(1)


def get_from_video():
    url = 'http://192.168.225.137:2000/old-video'
    cap = cv2.VideoCapture(url)
    while True:
        _, img = cap.read()
        cv2.imshow('Video from URL', img)
        cv2.waitKey(1)


if __name__ == '__main__':
    get_from_image()
    # get_from_video()
