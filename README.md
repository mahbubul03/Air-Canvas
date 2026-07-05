# Air Canvas ✋🎨

Draw in thin air using nothing but your webcam and your index finger. Air Canvas uses **MediaPipe** hand tracking to turn hand gestures into brush strokes, with an **eraser**, **undo history**, **PNG export**, and an **OCR-powered "beautify"** mode that turns your messy handwriting into clean typed text.

---

## Features

- ✍️ Draw with your index finger — tracked live via webcam
- 🖐️ Gesture controls — no mouse or keyboard needed while drawing
- 🧽 Eraser (fist gesture or `E` key)
- ↩️ Undo (`Z`)
- 💾 Save your canvas as a PNG (`S`)
- 🔤 "Beautify" — recognizes handwritten text with OCR and re-renders it in a clean font (`B`)
- 🎨 5 ink colors + adjustable thickness

---

## Demo Controls

| Gesture | Action |
|---|---|
| Index finger only up | Draw |
| Index + middle finger up | Pointer (move without drawing) |
| Fist (no fingers up) | Eraser at your palm |
| All 5 fingers up | Clear canvas (with cooldown) |

| Key | Action |
|---|---|
| `Q` | Quit |
| `C` | Clear canvas |
| `B` | Beautify text (OCR) |
| `E` | Toggle eraser mode |
| `Z` | Undo |
| `S` | Save canvas as PNG |
| `+` / `-` | Increase / decrease brush thickness |
| `G` / `R` / `U` / `Y` / `W` | Green / Red / Blue / Yellow / White ink |

---

## Requirements

- Python 3.9 – 3.11 (MediaPipe does not yet support all newer Python versions — 3.10 is the safest bet)
- A working webcam
- OS: Windows, macOS, or Linux

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/air-canvas.git
cd air-canvas
```

### 2. Create a virtual environment (recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

Create a `requirements.txt` with:

```
opencv-python
mediapipe
numpy
easyocr
Pillow
```

Then install:

```bash
pip install -r requirements.txt
```

> **Note:** `easyocr` will download its recognition model (~100 MB) the first time it runs, so the first launch may take a minute or two and needs an internet connection.

### 4. Run it

```bash
python air_canvas.py
```

A window should open showing your webcam feed. Hold up your index finger and start drawing!

Press `Q` at any time to quit.

---

## Troubleshooting

**Camera doesn't open / "Could not open webcam" error**
- Make sure no other application (Zoom, Teams, etc.) is using the camera.
- Try changing `cv2.VideoCapture(0)` to `cv2.VideoCapture(1)` in the script if you have multiple cameras.
- On macOS, grant camera permissions to your terminal/IDE in **System Settings → Privacy & Security → Camera**.

**`ModuleNotFoundError: No module named 'mediapipe'`**
- Confirm your virtual environment is activated, then re-run `pip install -r requirements.txt`.
- MediaPipe wheels aren't available for every Python version/platform combo — if install fails, try Python 3.10 in a fresh venv.

**Beautify mode doesn't render text / uses a fallback font**
- The script looks for `DejaVuSans-Bold.ttf` at a Linux system path. On Windows/macOS this font path won't exist, and it will silently fall back to a default (smaller, less pretty) font. To fix, update the font path in `run_beautify_async()` in `air_canvas.py` to a font that exists on your system, e.g.:
  - Windows: `C:/Windows/Fonts/arialbd.ttf`
  - macOS: `/System/Library/Fonts/Supplemental/Arial Bold.ttf`

**Low FPS / laggy tracking**
- Lower the capture resolution by changing `cap.set(3, 1280)` / `cap.set(4, 720)` to smaller values like `640` / `480`.
- Close other apps using the GPU/CPU heavily.

**Hand tracking feels reversed or the fist/thumb gesture is unreliable**
- The current gesture logic is tuned for a right hand facing the camera. Left-handed users or unusual wrist angles may see less reliable "fist" detection — this is a known limitation (see project notes / issues).

---

## Project Structure

```
air-canvas/
├── air_canvas.py       # Main application
├── requirements.txt    # Python dependencies
└── README.md
```

---

## Roadmap / Ideas

- [ ] Handedness-aware gesture detection (support left hands properly)
- [ ] On-screen color palette selectable by pointing instead of keyboard
- [ ] Pinch-to-adjust brush thickness
- [ ] Multi-hand support (draw with two hands / two colors)
- [ ] Export drawing history as a replay video

Contributions and PRs welcome!

---

## License

MIT — feel free to use, modify, and share.
