import sys
import select
import socket
import time
import requests
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# =============================
# CONFIG
# =============================
OLLAMA_URL = "http://localhost:11434/api/generate"

# =============================
# CONNECT TO JD ROBOT
# =============================
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 5005))

print("✅ Connected to JD Robot")

def send(cmd):
    client.send((cmd + "\n").encode())

def speak(text):
    text = text.replace('"', "'")[:120]
    send(f'SayEZB("{text}")')
    print("🤖:", text)
    # Block script until speaking finishes 
    # Approx 12 chars per sec + 0.5s pause
    time.sleep((len(text) / 12) + 0.5)

# =============================
# SERVO CONTROL
# =============================
def move_head_lr(pos):
    send(f"Servo(D1,{int(pos)})")

def move_head_ud(pos):
    send(f"Servo(D0,{int(pos)})")

def forward():
    send("Forward()")

def stop():
    send("Stop()")

# =============================
# 🤖 BOW GESTURE
# =============================
def bow():
    print("🙇 Bowing...")
    move_head_ud(120)
    time.sleep(0.5)
    move_head_ud(60)
    time.sleep(0.5)
    move_head_ud(90)

# =============================
# ✍️ DRAW SHAPES
# =============================
def draw_shape(shape):
    print(f"🏠 Drawing a {shape}...")
    speak(f"I am gripping the pen to draw a {shape}")
    
    # Initialize arm speeds
    send("ServoSpeed(D7, 3)")
    send("ServoSpeed(D8, 3)")
    
    # Head looks down at the paper
    send("Servo(D0, 130)") # Look down
    send("Servo(D1, 90)")  # Face forward
    
    # Grip pen (Right Gripper is D9)
    send("Servo(D9, 150)") # Close gripper
    time.sleep(3)
    
    # Lower pen to paper
    send("Servo(D7, 120)") # Lower shoulder to table
    send("Servo(D8, 100)") # Bend elbow slightly
    time.sleep(2)
    
    # Because the paper is static and the arm has limited DOF, 
    # we draw perfect shapes by having the robot use all its limbs to WALK the shape!
    if shape == "square":
        for _ in range(4):
            send("Forward()")
            time.sleep(2)
            send("Stop()")
            time.sleep(0.5)
            send("Right()")
            time.sleep(1.5) # Approximate time for a 90 degree turn
            send("Stop()")
            time.sleep(0.5)
    elif shape == "rectangle":
        for _ in range(2):
            # Long side
            send("Forward()")
            time.sleep(3)
            send("Stop()")
            time.sleep(0.5)
            send("Right()")
            time.sleep(1.5)
            send("Stop()")
            time.sleep(0.5)
            # Short side
            send("Forward()")
            time.sleep(1.5)
            send("Stop()")
            time.sleep(0.5)
            send("Right()")
            time.sleep(1.5)
            send("Stop()")
            time.sleep(0.5)
    elif shape == "triangle":
        for _ in range(3):
            send("Forward()")
            time.sleep(2)
            send("Stop()")
            time.sleep(0.5)
            # 120 degree turn
            send("Right()")
            time.sleep(2.0)
            send("Stop()")
            time.sleep(0.5)
    else: # House
        # Base (Square)
        for _ in range(4):
            send("Forward()")
            time.sleep(2)
            send("Stop()")
            time.sleep(0.5)
            send("Right()")
            time.sleep(1.5)
            send("Stop()")
            time.sleep(0.5)
        # Move forward slightly
        send("Forward()")
        time.sleep(2)
        send("Stop()")
        time.sleep(0.5)
        # 45 degree turn
        send("Right()")
        time.sleep(0.8)
        send("Stop()")
        time.sleep(0.5)
        # Roof Side 1
        send("Forward()")
        time.sleep(1.5)
        send("Stop()")
        time.sleep(0.5)
        # 90 deg turn at roof peak
        send("Right()")
        time.sleep(1.5)
        send("Stop()")
        time.sleep(0.5)
        # Roof Side 2
        send("Forward()")
        time.sleep(1.5)
        send("Stop()")
        time.sleep(0.5)
    
    # Lift pen, look up, and reset arms
    send("Servo(D7, 90)")
    send("Servo(D0, 90)") # Reset head ud
    time.sleep(1)
    
    # Release pen
    send("Servo(D9, 90)") # Open gripper
    time.sleep(1)
    
    speak(f"I have finished drawing the {shape}")

# =============================
# LLM
# =============================
def ask_llm(prompt):
    try:
        prompt = f"Answer in 1 short sentence: {prompt}"

        res = requests.post(OLLAMA_URL, json={
            "model": "phi3",
            "prompt": prompt,
            "stream": False
        }, timeout=60)

        return res.json().get("response", "No answer")

    except:
        return "Brain not responding"

# =============================
# 🎤 VOSK MIC & KEYBOARD
# =============================
import threading
import queue

model = Model(r"D:\JD\model\vosk-model-small-en-us-0.15\vosk-model-small-en-us-0.15")
recognizer = KaldiRecognizer(model, 16000)

input_queue = queue.Queue()

def keyboard_listener():
    while True:
        try:
            text = sys.stdin.readline().strip()
            if text:
                input_queue.put(text)
        except:
            break

keyboard_thread = threading.Thread(target=keyboard_listener, daemon=True)
keyboard_thread.start()

def listen_or_keyboard(duration=5):
    print(f"🎤 Listening for {duration} seconds... (or type your command)")
    
    text_result = ""
    keyboard_result = None
    
    def callback(indata, frames, time_info, status):
        nonlocal text_result
        if recognizer.AcceptWaveform(bytes(indata)):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                text_result += " " + text
                
    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=callback
    ):
        start_time = time.time()
        while time.time() - start_time < duration:
            # Check for keyboard input
            try:
                keyboard_result = input_queue.get_nowait()
                break
            except queue.Empty:
                time.sleep(0.1)

    text_result = text_result.strip()
    
    if keyboard_result:
        print("⌨️ Keyboard Input:", keyboard_result)
        return keyboard_result
    
    if text_result:
        print("🗣️ Mic Input:", text_result)
    return text_result

print("🚀 JD AI STARTED")

# =============================
# 🔥 START SEQUENCE
# =============================
bow()
speak("Hello I am JD Robot from D I T University and your personal assistant")

# =============================
# MAIN LOOP
# =============================
try:
    while True:
        speak("Listening")
        user = listen_or_keyboard(5)
        
        if user:
            print("💬 Final Input:", user)
            
            if user.lower() in ["exit", "stop"]:
                speak("Stopping system")
                break
                
            if "draw a house" in user.lower():
                draw_shape("house")
            elif "draw a square" in user.lower():
                draw_shape("square")
            elif "draw a rectangle" in user.lower():
                draw_shape("rectangle")
            elif "draw a triangle" in user.lower():
                draw_shape("triangle")
            else:
                reply = ask_llm(user)
                speak(reply)
        else:
            speak("No input detected")
            
        # Guarantee next listening starts in exactly 2 seconds
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopping manually...")

# =============================
# CLEANUP
# =============================
client.close()