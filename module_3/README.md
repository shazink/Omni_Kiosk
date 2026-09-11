# Module 3: Document Computer Vision Scanner & Spatial Guidance

Assists citizens (especially blind or visually impaired) in positioning and capturing physical ID cards and paper documents under the kiosk camera.

---

## Directory Structure

```
module_3/
├── __init__.py                     # Package exports
├── document_scanner.py             # Primary Module 3 execution engine
├── generate_test_id.py             # Synthetic Aadhaar card image generator
├── test_module3_vision_ocr.py      # Comprehensive 13-part automated test suite
├── .env                            # Scanner configuration settings
└── README.md                       # Module documentation
```

---

## Pipeline

```
Video Stream (60 FPS) -> OpenCV Grayscale + Gaussian Blur
    -> Canny Edge Detection -> Find Contours (Area > 20% of frame)
    -> Polygon Approximation (approxPolyDP) -> Quadrilateral Bounding Box
    -> Spatial Vector Math + Sharpness Evaluator
    -> Active Spatial Voice Prompts ("Move left 5cm", "Hold steady")
    -> Auto-Snapshot (Stability > 15 frames + Sharpness > 85%)
       OR Voice Trigger ("Capture now")
    -> Local On-Device Tesseract OCR
    -> Extracts: 12-digit Aadhaar UID, Name, DOB
```

---

## Quick Start

### 1. Synthetic Demo (no camera needed)
```bash
python module_3/document_scanner.py
```
Or with custom identity:
```bash
python module_3/document_scanner.py --name "Arun Kumar" --aadhaar "987654321098"
```

### 2. Live Camera Mode (requires OpenCV)
```bash
python module_3/document_scanner.py --mode camera
```

### 3. Generate Test Aadhaar Card
```bash
python module_3/generate_test_id.py --name "Arun Kumar" --aadhaar "987654321098"
```

### 4. Run Automated Tests
```bash
python module_3/test_module3_vision_ocr.py
```

---

## Key Classes

| Class | Responsibility |
|---|---|
| `DocumentContourDetector` | OpenCV contour tracing with stdlib fallback |
| `SpatialAlignmentEngine` | ΔX, ΔY offset and skew angle computation |
| `SpatialGuidanceEngine` | Directional voice prompt generation |
| `SharpnessEvaluator` | Laplacian variance sharpness scoring |
| `AutoSnapshotController` | Stability tracking + voice override capture |
| `LocalOCR` | Tesseract OCR with regex field extraction |
| `SyntheticFrameGenerator` | Test frame generation without camera hardware |
| `DocumentScannerSession` | Full pipeline orchestrator |

---

## Environment Variables

All parameters are configurable via `.env` — zero hardcoding:

| Variable | Default | Description |
|---|---|---|
| `SCANNER_SHARPNESS_THRESHOLD` | 85.0 | Minimum sharpness % to allow capture |
| `SCANNER_STABILITY_FRAMES` | 15 | Consecutive stable frames before auto-snap |
| `SCANNER_OFFSET_THRESHOLD_PX` | 40 | Pixel offset triggering directional guidance |
| `SCANNER_SKEW_THRESHOLD_DEG` | 5.0 | Degree threshold triggering rotation guidance |
| `SCANNER_MIN_CONTOUR_AREA_RATIO` | 0.20 | Minimum document area as fraction of frame |
| `SCANNER_CAMERA_DEVICE` | 0 | Camera device index |
| `SCANNER_FRAME_WIDTH` | 640 | Capture frame width |
| `SCANNER_FRAME_HEIGHT` | 480 | Capture frame height |
