import os
import argparse
import cv2
import numpy as np
import time
from threading import Thread
import importlib.util

# Function to print object detection results
def print_output(message):
    print('{}'.format(message))

# Initialize webcam video stream class
class VideoStream:
    """Camera object that controls video streaming from the webcam"""
    def _init_(self, resolution=(640, 480), framerate=30):
        # Initialize the camera and the camera image stream
        self.stream = cv2.VideoCapture(0)
        ret = self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret = self.stream.set(3, resolution[0])
        ret = self.stream.set(4, resolution[1])

        # Check if the video capture has been initialized correctly
        if not self.stream.isOpened():
            print("Error: Could not open video device.")
            exit()

        # Read first frame from the stream
        (self.grabbed, self.frame) = self.stream.read()

        # Check if the first frame was captured successfully
        if not self.grabbed or self.frame is None or self.frame.size == 0:
            print("Error: Frame capture failed or the frame is empty.")
            self.stopped = True
        else:
            self.stopped = False

    def start(self):
        # Start the thread that reads frames from the video stream
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        # Keep looping until the camera is stopped
        while True:
            if self.stopped:
                # Close camera resources
                self.stream.release()
                return

            # Grab the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

            # Check if the frame was captured successfully
            if not self.grabbed or the frame is None or the frame.size == 0:
                print("Error: Frame capture failed or the frame is empty.")
                self.stop()

    def read(self):
        # Return the most recent frame
        return self.frame

    def stop(self):
        # Indicate that the camera and thread should be stopped
        self.stopped = True

# Define and parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('--modeldir', help='Folder the .tflite file is located in', required=True)
parser.add_argument('--graph', help='Name of the .tflite file, if different than detect.tflite', default='detect.tflite')
parser.add_argument('--labels', help='Name of the labelmap file, if different than labelmap.txt', default='labelmap.txt')
parser.add_argument('--threshold', help='Minimum confidence threshold for displaying detected objects', default=0.5)
parser.add_argument('--resolution', help='Desired webcam resolution in WxH', default='640x480')
parser.add_argument('--edgetpu', help='Use Coral Edge TPU Accelerator to speed up detection', action='store_true')

args = parser.parse_args()

MODEL_NAME = args.modeldir
GRAPH_NAME = args.graph
LABELMAP_NAME = args.labels
min_conf_threshold = float(args.threshold)
resW, resH = args.resolution.split('x')
imW, imH = int(resW), int(resH)
use_TPU = args.edgetpu

# Load TensorFlow Lite model
pkg = importlib.util.find_spec('tflite_runtime')
if pkg:
    from tflite_runtime.interpreter import Interpreter
    if use_TPU:
        from tflite_runtime.interpreter import load_delegate
else:
    from tensorflow.lite.python.interpreter import Interpreter
    if use_TPU:
        from tensorflow.lite.python.interpreter import load_delegate

if use_TPU:
    if GRAPH_NAME == 'detect.tflite':
        GRAPH_NAME = 'edgetpu.tflite'
CWD_PATH = os.getcwd()

# Path to .tflite file and label map
PATH_TO_CKPT = os.path.join(CWD_PATH, MODEL_NAME, GRAPH_NAME)
PATH_TO_LABELS = os.path.join(CWD_PATH, MODEL_NAME, LABELMAP_NAME)

# Load the label map
with open(PATH_TO_LABELS, 'r') as f:
    labels = [line.strip() for line in f.readlines()]

if labels[0] == '???':
    del(labels[0])

if use_TPU:
    interpreter = Interpreter(model_path=PATH_TO_CKPT, experimental_delegates=[load_delegate('libedgetpu.so.1.0')])
else:
    interpreter = Interpreter(model_path=PATH_TO_CKPT)

interpreter.allocate_tensors()
# Get model details
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
height = input_details[0]['shape'][1]
width = input_details[0]['shape'][2]

floating_model = (input_details[0]['dtype'] == np.float32)

input_mean = 127.5
input_std = 127.5

# Initialize frame rate calculation
frame_rate_calc = 1
freq = cv2.getTickFrequency()

# Initialize video stream
videostream = VideoStream(resolution=(imW, imH), framerate=30).start()
time.sleep(1)

# Main detection loop
while True:
    # Start timer
    t1 = cv2.getTickCount()

    # Grab frame from video stream
    frame1 = videostream.read()

    # Check if the frame was captured successfully
    if frame1 is None or frame1.size == 0:
        print("Error: Frame capture failed or the frame is empty.")
        break

    # Resize and normalize input
    frame_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
    frame_resized = cv2.resize(frame_rgb, (width, height))
    input_data = np.expand_dims(frame_resized, axis=0)

    if floating_model:
        input_data = (np.float32(input_data) - input_mean) / input_std

    # Perform the detection
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    # Get detection results
    boxes = interpreter.get_tensor(output_details[0]['index'])[0]
    classes = interpreter.get_tensor(output_details[1]['index'])[0]
    scores = interpreter.get_tensor(output_details[2]['index'])[0]

    # Process results - Only detect "person"
    for i in range(len(scores)):
        if ((scores[i] > min_conf_threshold) and (scores[i] <= 1.0)):
            # Check if the detected class is "person" (usually class 0 in COCO dataset)
            if labels[int(classes[i])] == 'person':
                print_output("Face detected")  # Print face detected message

    # Add a small sleep to avoid an infinite fast loop
    time.sleep(0.1)

# Clean up
videostream.stop()
