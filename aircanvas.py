"""
Air Canvas - Smart Text Beautification (v2)
---------------------------------------------
Draw in the air with your index finger, tracked via a webcam + MediaPipe.
By-MAHBUBUL ISLAM

Gestures:
  - Index finger only up      -> Draw
  - Index + Middle up         -> Pointer (move without drawing)
  - Fist (no fingers up)      -> Eraser (erases near your palm)
  - All 5 fingers up          -> Clear whole canvas (debounced)

Keys:
  Q - Quit            C - Clear canvas       B - Beautify text (OCR)
  E - Toggle eraser   Z - Undo               S - Save canvas as PNG
  +/- - Thickness      G/R/U/Y/W - Green/Red/Blue/Yellow/White ink
"""

import cv2
import mediapipe as mp
import numpy as np
import easyocr
import time
import threading
import os
from collections import deque
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

print("Loading OCR model (first run may take a moment)...")
reader = easyocr.Reader(['en'])

# ---------------------------------------------------------------------------
# Where should saved PNGs go?
# Leave as None to save in the same folder as this script (a "saved_drawings"
# subfolder gets created automatically). Or set your own path, e.g.:
#   SAVE_DIR = "C:/Users/you/Pictures/AirCanvas"      (Windows)
#   SAVE_DIR = "/Users/you/Pictures/AirCanvas"        (macOS)
#   SAVE_DIR = "/home/you/Pictures/AirCanvas"         (Linux)
# ---------------------------------------------------------------------------
SAVE_DIR = None

if SAVE_DIR is None:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, "saved_drawings")
else:
    OUTPUT_DIR = SAVE_DIR

COLORS = {
    "g": ("Green", (0, 255, 0)),
    "r": ("Red", (0, 0, 255)),
    "u": ("Blue", (255, 0, 0)),
    "y": ("Yellow", (0, 255, 255)),
    "w": ("White", (255, 255, 255)),
}

canvas = None
undo_stack = deque(maxlen=20)
smooth_pts = deque(maxlen=5)  # for jitter smoothing

prev_x, prev_y = 0, 0
drawing_color = COLORS["g"][1]
thickness = 5
eraser_thickness = 40
mode = "draw"
eraser_on = False

last_beautify_time = 0
beautify_lock = threading.Lock()
beautify_busy = False
beautify_result_canvas = None

last_clear_time = 0
CLEAR_COOLDOWN = 1.5  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def smoothed_point(x, y):
    """Average recent points to reduce jitter."""
    smooth_pts.append((x, y))
    xs = sum(p[0] for p in smooth_pts) / len(smooth_pts)
    ys = sum(p[1] for p in smooth_pts) / len(smooth_pts)
    return int(xs), int(ys)


def push_undo(current_canvas):
    undo_stack.append(current_canvas.copy())


def composite(frame, canvas):
    """Overlay canvas onto frame using a mask so empty areas stay a clean camera feed."""
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    mask = gray > 0
    out = frame.copy()
    if mask.any():
        blended = cv2.addWeighted(frame, 0.25, canvas, 0.9, 0)
        out[mask] = blended[mask]
    return out


def run_beautify_async(canvas_snapshot):
    """Runs OCR + redraw on a background thread so the camera feed doesn't freeze."""
    global beautify_busy, beautify_result_canvas

    gray = cv2.cvtColor(canvas_snapshot, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

    try:
        result = reader.readtext(thresh, detail=1, paragraph=True)
    except Exception as e:
        print("OCR error:", e)
        result = []

    clean_canvas = np.zeros_like(canvas_snapshot)

    if result:
        pil_img = Image.fromarray(clean_canvas)
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except Exception:
            font = ImageFont.load_default()

        for (bbox, text, prob) in result:
            if prob > 0.5 and len(text.strip()) > 1:
                x, y = int(bbox[0][0]), int(bbox[0][1])
                draw.text((x, y), text, font=font, fill=(255, 255, 255))
        clean_canvas = np.array(pil_img)

    with beautify_lock:
        beautify_result_canvas = clean_canvas
        beautify_busy = False


def trigger_beautify():
    global last_beautify_time, beautify_busy
    if beautify_busy or time.time() - last_beautify_time < 2:
        return
    last_beautify_time = time.time()
    beautify_busy = True
    push_undo(canvas)
    t = threading.Thread(target=run_beautify_async, args=(canvas.copy(),), daemon=True)
    t.start()


def save_canvas(display_img):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fname = os.path.join(OUTPUT_DIR, f"air_canvas_{int(time.time())}.png")
    cv2.imwrite(fname, display_img)
    print(f"Saved: {fname}")
    return fname


def draw_ui(img, fps):
    h, w = img.shape[:2]
    cv2.putText(img, f"Mode: {mode.upper()}  FPS: {fps:.0f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, "B:Beautify C:Clear E:Eraser Z:Undo S:Save +/-:Size Q:Quit",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    # color swatches
    x0 = w - 40
    for key, (name, bgr) in COLORS.items():
        cv2.rectangle(img, (x0 - 25, 10), (x0, 35), bgr, -1)
        if bgr == drawing_color and not eraser_on:
            cv2.rectangle(img, (x0 - 25, 10), (x0, 35), (255, 255, 255), 2)
        x0 -= 35

    if eraser_on:
        cv2.putText(img, "ERASER ACTIVE", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
cap = cv2.VideoCapture(0)
cap.set(3, 1280)
cap.set(4, 720)

if not cap.isOpened():
    raise RuntimeError("Could not open webcam. Check camera permissions/index.")

print("Air Canvas Started! Press Q to quit.")

fps_time = time.time()
fps = 0
was_drawing = False

while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    if canvas is None:
        canvas = np.zeros((h, w, 3), np.uint8)

    # Pull in any finished beautify result
    with beautify_lock:
        if beautify_result_canvas is not None:
            canvas = beautify_result_canvas
            beautify_result_canvas = None

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    currently_drawing = False

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            lm = hand_landmarks.landmark

            index_tip = (int(lm[8].x * w), int(lm[8].y * h))
            palm = (int(lm[9].x * w), int(lm[9].y * h))

            fingers_up = [
                lm[4].y < lm[3].y,
                lm[8].y < lm[6].y,
                lm[12].y < lm[10].y,
                lm[16].y < lm[14].y,
                lm[20].y < lm[18].y,
            ]

            if all(fingers_up):
                mode = "clear"
                if time.time() - last_clear_time > CLEAR_COOLDOWN:
                    push_undo(canvas)
                    canvas = np.zeros((h, w, 3), np.uint8)
                    last_clear_time = time.time()
                    cv2.putText(frame, "Canvas Cleared!", (50, 120),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                prev_x, prev_y = 0, 0
                smooth_pts.clear()

            elif not any(fingers_up):
                # Fist -> eraser at palm location
                mode = "erase"
                cv2.circle(canvas, palm, eraser_thickness, (0, 0, 0), -1)
                cv2.circle(frame, palm, eraser_thickness, (0, 0, 255), 2)
                prev_x, prev_y = 0, 0
                smooth_pts.clear()

            elif fingers_up[1] and not fingers_up[2]:
                mode = "draw"
                x, y = smoothed_point(*index_tip)
                if not was_drawing:
                    push_undo(canvas)
                if prev_x == 0 and prev_y == 0:
                    prev_x, prev_y = x, y
                color = (0, 0, 0) if eraser_on else drawing_color
                t = eraser_thickness if eraser_on else thickness
                cv2.line(canvas, (prev_x, prev_y), (x, y), color, t)
                prev_x, prev_y = x, y
                currently_drawing = True

            else:
                mode = "pointer"
                prev_x, prev_y = 0, 0
                smooth_pts.clear()
    else:
        prev_x, prev_y = 0, 0
        smooth_pts.clear()

    was_drawing = currently_drawing

    img = composite(frame, canvas)

    now = time.time()
    fps = 0.9 * fps + 0.1 * (1.0 / max(now - fps_time, 1e-6))
    fps_time = now

    draw_ui(img, fps)
    cv2.imshow("Air Canvas - Smart Text Beautification", img)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        push_undo(canvas)
        canvas = np.zeros((h, w, 3), np.uint8)
    elif key == ord('b'):
        trigger_beautify()
    elif key == ord('e'):
        eraser_on = not eraser_on
    elif key == ord('z'):
        if undo_stack:
            canvas = undo_stack.pop()
    elif key == ord('s'):
        save_canvas(img)
    elif key in (ord('+'), ord('=')):
        thickness = min(thickness + 2, 40)
    elif key in (ord('-'), ord('_')):
        thickness = max(thickness - 2, 1)
    elif chr(key) in COLORS:
        drawing_color = COLORS[chr(key)][1]
        eraser_on = False

cap.release()
cv2.destroyAllWindows()