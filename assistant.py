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

# =============================
# SERVO CONTROL
# =============================
def move_head_lr(pos):
    send(f"Servo(D0,{int(pos)})")

def move_head_ud(pos):
    send(f"Servo(D1,{int(pos)})")

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
    
    # Use all motors: stabilize the legs to stand straight (not leaning or sitting)
    # Right Leg
    send("Servo(D16, 90)")
    send("Servo(D17, 90)")
    send("Servo(D18, 90)")
    # Left Leg 
    send("Servo(D12, 90)")
    send("Servo(D13, 90)")
    send("Servo(D14, 90)")
    
    # Use all motors: Head looks down at the paper, left arm balances
    send("Servo(D0, 90)") # Face forward
    send("Servo(D1, 130)") # Look down
    send("Servo(D4, 110)") # Left arm back
    send("Servo(D5, 90)")
    
    # Grip pen (Right Gripper is D9)
    send("Servo(D9, 150)") # Close gripper
    # Hold pen for at least 3 seconds before starting as requested
    time.sleep(3)
    
    # Arm sequence (Right Upper Arm D7, Right Forearm D8)
    # Move to starting position (lower shoulder to flat surface)
    send("Servo(D7, 100)")
    send("Servo(D8, 90)")
    time.sleep(1)
    
    # Use much larger angle ranges (e.g. 60 to 140) to draw big recognizable shapes
    if shape == "square":
        send("Servo(D7, 70)")
        send("Servo(D8, 70)")
        time.sleep(1)
        send("Servo(D8, 130)")
        time.sleep(1.5)
        send("Servo(D7, 130)")
        time.sleep(1.5)
        send("Servo(D8, 70)")
        time.sleep(1.5)
        send("Servo(D7, 70)")
        time.sleep(1.5)
    elif shape == "rectangle":
        send("Servo(D7, 60)")
        send("Servo(D8, 60)")
        time.sleep(1)
        send("Servo(D8, 140)")
        time.sleep(1.5)
        send("Servo(D7, 120)")
        time.sleep(1)
        send("Servo(D8, 60)")
        time.sleep(1.5)
        send("Servo(D7, 60)")
        time.sleep(1)
    elif shape == "triangle":
        send("Servo(D7, 70)")
        send("Servo(D8, 100)")
        time.sleep(1)
        send("Servo(D7, 130)")
        send("Servo(D8, 140)")
        time.sleep(1.5)
        send("Servo(D8, 60)")
        time.sleep(1.5)
        send("Servo(D7, 70)")
        send("Servo(D8, 100)")
        time.sleep(1.5)
    else: # House
        # Walls (Square)
        send("Servo(D7, 90)")
        send("Servo(D8, 70)")
        time.sleep(1)
        send("Servo(D8, 130)")
        time.sleep(1)
        send("Servo(D7, 130)")
        time.sleep(1)
        send("Servo(D8, 70)")
        time.sleep(1)
        send("Servo(D7, 90)")
        time.sleep(1)
        # Roof (Triangle)
        send("Servo(D7, 60)")
        send("Servo(D8, 100)")
        time.sleep(1)
        send("Servo(D7, 90)")
        send("Servo(D8, 130)")
        time.sleep(1)
    
    # Lift pen, look up, and reset left arm
    send("Servo(D7, 90)")
    send("Servo(D1, 90)")
    send("Servo(D4, 90)")
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
model = Model(r"D:\JD\model\vosk-model-small-en-us-0.15\vosk-model-small-en-us-0.15")
recognizer = KaldiRecognizer(model, 16000)

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
            i, o, e = select.select([sys.stdin], [], [], 0.1)
            if i:
                keyboard_result = sys.stdin.readline().strip()
                break

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