import cv2
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
# 🎤 VOSK MIC (5 SEC LISTEN)
# =============================
model = Model(r"D:\JD\model\vosk-model-small-en-us-0.15\vosk-model-small-en-us-0.15")
recognizer = KaldiRecognizer(model, 16000)

def listen_5sec():
    print("🎤 Listening for 5 seconds...")

    text_result = ""

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
        time.sleep(5)   # 🔥 ONLY 5 SECONDS

    text_result = text_result.strip()
    print("🗣️ Final Mic Input:", text_result)

    return text_result

# =============================
# CAMERA
# =============================
cap = cv2.VideoCapture(0)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# =============================
# VARIABLES
# =============================
servo_lr = 90
servo_ud = 90
smooth = 0.2
last_talk = 0
cooldown = 6

print("🚀 JD AI STARTED")

# =============================
# 🔥 START SEQUENCE
# =============================
bow()
speak("Hello I am JD Robot from D I T University and your personal assistant")

# =============================
# MAIN LOOP
# =============================
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) > 0:
        (x, y, fw, fh) = faces[0]

        cx = x + fw // 2
        cy = y + fh // 2

        cv2.rectangle(frame, (x,y), (x+fw,y+fh), (0,255,0), 2)

        # =============================
        # HEAD TRACKING
        # =============================
        target_lr = 40 + (cx / w) * 100
        target_ud = 40 + (cy / h) * 100

        servo_lr = smooth * target_lr + (1 - smooth) * servo_lr
        servo_ud = smooth * target_ud + (1 - smooth) * servo_ud

        move_head_lr(servo_lr)
        move_head_ud(servo_ud)

        # FOLLOW
        if fw < 80:
            forward()
        elif fw > 150:
            stop()

        # =============================
        # AI INTERACTION
        # =============================
        if fw > 150 and time.time() - last_talk > cooldown:

            speak("Listening")

            user = listen_5sec()

            # fallback
            if not user:
                user = input("⌨️ Type: ")

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

            last_talk = time.time()

    else:
        stop()

    cv2.imshow("JD ROBOT", frame)

    if cv2.waitKey(1) == 27:
        break

# =============================
# CLEANUP
# =============================
cap.release()
cv2.destroyAllWindows()
client.close()