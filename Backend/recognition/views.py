from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.shortcuts import render
import cv2
import os
import threading
import time, csv
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

def login(request):
    return render(request, 'login.html')

def signup(request):
    return render(request, 'signup.html')

import json
import os
from django.shortcuts import render, redirect
from django.http import JsonResponse

def userlogin(request):
    if request.method == 'POST':
        # Get username and password from the POST request
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Path to the users.json file
        json_file_path = os.path.join(os.path.dirname(__file__), 'users.json')
        
        try:
            # Load users from the JSON file
            with open(json_file_path, 'r') as json_file:
                users_data = json.load(json_file)
            
            # Validate credentials
            if username in users_data and users_data[username] == password:
                # Redirect to the live_feed view on successful login
                return redirect('live_feed')
            else:
                # Return an error message on invalid login
                return render(request, 'login.html', {'error': 'Invalid username or password.'})
        except FileNotFoundError:
            return render(request, 'login.html', {'error': 'Users database not found.'})
        except json.JSONDecodeError:
            return render(request, 'login.html', {'error': 'Error reading users database.'})
    return render(request, 'login.html')


def usersignup(request):
    if request.method == 'POST':
        # Get the username and password from the POST request
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Path to the users.json file
        json_file_path = os.path.join(os.path.dirname(__file__), 'users.json')

        try:
            # Read existing data from the JSON file
            if os.path.exists(json_file_path):
                with open(json_file_path, 'r') as json_file:
                    users_data = json.load(json_file)
            else:
                users_data = {}

            # Add the new user credentials to the data
            if username in users_data:
                return JsonResponse({'status': 'error', 'message': 'Username already exists.'})
            
            users_data[username] = password

            # Write the updated data back to the JSON file
            with open(json_file_path, 'w') as json_file:
                json.dump(users_data, json_file, indent=4)
            
            return redirect('login')

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Error reading or writing users database.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

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

# Initialize webcam dynamically
def get_video_capture():
    """
    Dynamically initializes and returns the video capture object.
    Ensures the webcam can be restarted if released earlier.
    """
    global video_capture
    if not video_capture or not video_capture.isOpened():
        video_capture = cv2.VideoCapture(0)
    return video_capture

# Modify the live_video generator
def gen_frames():
    """
    Generates video frames for the live feed.
    Dynamically initializes the webcam if not already initialized.
    """
    while True:
        video_capture = get_video_capture()  # Ensure webcam is initialized
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
def factory(frame, tim, tolerance=0.6):
    """
    Processes the captured frame to recognize and mark known faces.
    Logs the date, time, and face identification details in a CSV file.
    """
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    # CSV file path
    csv_file_path = os.path.join(settings.BASE_DIR, 'Backend/face_logs.csv')

    # Open the CSV file in append mode
    with open(csv_file_path, mode='a', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        # Iterate through detected faces
        for face_encoding, face_location in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=tolerance)
            name = "Unknown"

            # Find the best match
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            best_match_index = None if not face_distances.size else face_distances.argmin()
            if best_match_index is not None and matches[best_match_index]:
                name = known_face_names[best_match_index]

            # Draw face box and label
            top, right, bottom, left = face_location
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 0), 2)

            # Log the detection
            csv_writer.writerow([time.strftime("%Y-%m-%d"), time.strftime("%H:%M:%S"), name])

    # Save the processed frame
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

            # Process the frame with a specified tolerance and store it
            factory(frame, tim, tolerance=0.5)

            # Dynamically serve the file via URL
            image_url = f'/static/captured_frames/{file_name}'
            processed_image_url = f'/static/processed_frames/processed_{tim}.jpg'
            return JsonResponse({'image_url': image_url, 'processed_image_url': processed_image_url})
    return JsonResponse({'error': 'Failed to capture frame'}, status=500)

def release_camera(request):
    """
    Releases the video capture object when the user navigates away.
    """
    global video_capture
    if video_capture.isOpened():
        video_capture.release()
        return JsonResponse({'status': 'success', 'message': 'Camera released successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Camera was not active.'}, status=500)
