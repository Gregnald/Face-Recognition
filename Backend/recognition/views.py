from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
import cv2
import os
import threading
import time
import face_recognition
from django.conf import settings

# Directories for frames
CAPTURED_FRAMES_DIR = os.path.join(settings.BASE_DIR, 'Frontend/static/captured_frames')
PROCESSED_FRAMES_DIR = os.path.join(settings.BASE_DIR, 'Frontend/static/processed_frames')

# Ensure directories exist
os.makedirs(CAPTURED_FRAMES_DIR, exist_ok=True)
os.makedirs(PROCESSED_FRAMES_DIR, exist_ok=True)

# Initialize video capture and threading lock
video_capture = cv2.VideoCapture(0)
lock = threading.Lock()

# Known face encodings and names
known_face_encodings = []
known_face_names = []

def load_known_faces():
    """
    Load all known faces from the directory `Faces`.
    """
    KNOWN_FACES_DIR = os.path.join(settings.BASE_DIR, "Faces")
    if not os.path.exists(KNOWN_FACES_DIR):
        print("No known faces directory found.")
        return

    for file_name in os.listdir(KNOWN_FACES_DIR):
        if file_name.lower().endswith(('jpg', 'jpeg')):
            file_path = os.path.join(KNOWN_FACES_DIR, file_name)
            image = face_recognition.load_image_file(file_path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(os.path.splitext(file_name)[0])
    print(f"Loaded {len(known_face_encodings)} known faces.")

# Load known faces at the start of the server
load_known_faces()

def home(request):
    return render(request, 'index.html')

def live_feed(request):
    return render(request, 'live_feed.html')

def gen_frames():
    while True:
        with lock:
            success, frame = video_capture.read()
            if not success:
                break
            _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def live_video(request):
    return StreamingHttpResponse(gen_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

import time  # Import time module for the delay

# Add the new function here
def factory(frame, tim):
    """
    Processes the captured frame to recognize and mark known faces.
    The processed frame is then saved to the processed_frames directory.
    """
    # Find all face locations and encodings in the current frame
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    for face_encoding, face_location in zip(face_encodings, face_locations):
        # Compare the face with known faces
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        # Find the best match for the detected face
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = None if not face_distances.size else face_distances.argmin()
        
        if best_match_index is not None and matches[best_match_index]:
            name = known_face_names[best_match_index]

        # Draw a box around the face and label it
        top, right, bottom, left = face_location
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 0), 2)

    # Save the processed frame with the same timestamp
    processed_file_name = f'processed_{tim}.jpg'
    processed_file_path = os.path.join(PROCESSED_FRAMES_DIR, processed_file_name)
    cv2.imwrite(processed_file_path, frame)

    return processed_file_path

# Update the capture_frame function to call factory()
def capture_frame(request):
    with lock:  # Lock access to the video capture
        success, frame = video_capture.read()
        if success:
            # Delete previous captured files
            for file in os.listdir(CAPTURED_FRAMES_DIR):
                if file.startswith('captured_'):
                    os.remove(os.path.join(CAPTURED_FRAMES_DIR, file))
            for file in os.listdir(PROCESSED_FRAMES_DIR):
                if file.startswith('processed_'):
                    os.remove(os.path.join(PROCESSED_FRAMES_DIR, file))

            # Save the new captured frame
            tim = int(time.time())
            file_name = f'captured_{tim}.jpg'
            file_path = os.path.join(CAPTURED_FRAMES_DIR, file_name)
            cv2.imwrite(file_path, frame)

            # Process the frame and store it
            factory(frame, tim)

            # Dynamically serve the file via URL
            image_url = f'/static/captured_frames/{file_name}'
            processed_image_url = f'/static/processed_frames/processed_{tim}.jpg'
            return JsonResponse({'image_url': image_url, 'processed_image_url': processed_image_url})
    return JsonResponse({'error': 'Failed to capture frame'}, status=500)