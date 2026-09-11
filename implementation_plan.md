# OmniKiosk: End-to-End Granular Implementation Plan

OmniKiosk is an autonomous, accessibility-first civic service terminal engineered for public administration (government, healthcare, civic portals). It enables blind, low-vision, deaf, non-verbal, and motor-impaired citizens to discover, fill, and submit official applications without manual barriers and with zero risk of cloud PII exposure.

---

## 1. Architectural Architecture & Feature Matrix

Every feature from the specification is accounted for in this plan:

| Feature / Subsystem | Technical Mechanism | Implementation File / Component |
|---|---|---|
| **Voice-Wake Pipeline** | Low-power WebAssembly/offline listener targeting *"Help me register"* | `local_form_filler.py` & `kiosk_hardware_sim.py` |
| **Privacy Display Dimming** | Screen drops to 0% brightness or neutral privacy shield upon voice wake | `mock_edistrict/static/css/portal.css` & UI controller |
| **Directional Audio & TTS** | Contextual speech prompts via local TTS engine (for blind/low-vision) | `local_form_filler.py` (`SpeechEngine`) |
| **On-Screen Sign Language Button** | Dedicated button (`#btnSignLanguage`: *"Start Sign Language Input"*) on the portal header | `mock_edistrict/static/js/kiosk_ui.js` |
| **Triple-Tap Screen Trigger** | Global listener detecting 3 rapid taps (<700ms) anywhere on glass | `mock_edistrict/static/js/kiosk_ui.js` & `kiosk_hardware_sim.py` |
| **High-Contrast Visual UI** | Shifts to high-contrast dark theme (pure black & high-vis yellow) with visual text cards & prompts | `mock_edistrict/static/css/high_contrast.css` |
| **Sign Language & Hand Tracking** | MediaPipe / `sign/translate` hand tracking interpreting citizen signs, fingerspelling & gestures | `vision_gesture_engine.py` |
| **Wheelchair Height Adaptation** | Ultrasonic range sensor drops canvas to lower 33% of display | `kiosk_hardware_sim.py` & CSS transform |
| **Document Contour Detection** | OpenCV real-time edge & contour tracing on video feed | `document_scanner.py` |
| **Active Spatial Audio Guidance** | Voice vectors: *"Move left 5cm"*, *"Tilt up"*, *"Hold steady"* | `document_scanner.py` (`SpatialGuidance`) |
| **Auto-Snapshot & Voice Override** | Snap on boundary stability & sharpness $>85\%$, or spoken *"Capture now"* | `document_scanner.py` |
| **Local OCR & Barcode Extraction**| Tesseract / local character recognition for IDs, names, dates, barcodes | `document_scanner.py` (`LocalOCR`) |
| **Dual-Tier Request Router** | Dispatches PII to Tier 1 local SLM and generic queries to Tier 2 cloud | `request_router.py` |
| **Tier 1: On-Device Edge SLM** | Fully offline quantized SLM / ONNX parsing natural narrative & signs to schema | `local_form_filler.py` (`EdgeSLM`) |
| **Tier 2: Cloud Doubt-Clearing** | Groq / Gemini API with strict PII stripper returning 2-sentence plain text on visual cards | `cloud_navigator.py` (`DoubtClearingEngine`) |
| **Mock Civic Portal (Port 3000)** | e-District Kerala with income, disability, and community forms | `mock_edistrict/server.py` |
| **Required Field Identifiers** | `#txtApplicantName`, `#txtAadhaarNo`, `#ddlDistrict`, `#ddlTaluk`, etc. | `mock_edistrict/forms/*.html` |
| **Downloadable Pro-formas** | `self-declaration-affidavit.pdf`, `medical-board-assessment.pdf` | `mock_edistrict/docs/*` |
| **Knowledge Base (RAG)** | `citizen-charter.md`, `acceptable-proofs.json` | `mock_edistrict/kb/*` |
| **Dynamic Receipt Generator** | `KL-EDIST-2026-XXXX` tracking ID, timestamp, office, barcode/QR | `mock_edistrict/receipts/acknowledgement-slip.html` |
| **Browser Injection (Playwright)** | Autonomous agentic DOM populator for text, select, radio, and files | `local_form_filler.py` (`DOMInjector`) |
| **Critic Verification Guardrail** | Regex audit (12-digit Aadhaar, IFSC, phone) & mandatory checks | `local_form_filler.py` (`CriticAgent`) |
| **Supervisor Human-in-the-Loop** | Audio readback ("Submit") OR visual review card + Thumbs-up gesture confirmation | `local_form_filler.py` (`SupervisorAgent`) |
| **Ephemeral Memory Flush** | Secure buffer zeroization (`sodium_memzero` / memory purge) | `local_form_filler.py` (`EphemeralPurge`) |
| **Inactivity Departure Auto-Scrub** | Ultrasonic sensor detects citizen departure -> 10s security purge | `kiosk_hardware_sim.py` |

---

## 2. Project Directory Layout

All files will be structured under the project directory:

```
omnikiosk/
├── mock_edistrict/                           # PART 1: Civic Service Web Portal (Port 3000)
│   ├── server.py                             # Async HTTP server serving forms, docs, receipts
│   ├── static/
│   │   ├── css/
│   │   │   ├── portal.css                    # Official Kerala e-District styling
│   │   │   └── high_contrast.css             # High-contrast accessibility theme (black & yellow)
│   │   └── js/
│   │       ├── kiosk_ui.js                   # Header '#btnSignLanguage' button, triple-tap & privacy listeners
│   │       ├── visual_cards.js               # High-contrast visual guidance & doubt-clearing display cards
│   │       └── portal.js                     # Dynamic cascading dropdowns (District -> Taluk -> Village)
│   ├── forms/
│   │   ├── income-certificate.html           # Target Form 1: Exact IDs (#txtApplicantName, #txtAadhaarNo...)
│   │   ├── disability-pension.html           # Target Form 2: (#applicantName, #aadhaarNo, #disabilityPercent...)
│   │   └── community-certificate.html        # Target Form 3: Religion, Caste, Proof upload
│   ├── docs/
│   │   ├── self-declaration-affidavit.pdf    # Downloadable pro-forma template
│   │   └── medical-board-assessment.pdf      # Disability assessment pro-forma
│   ├── kb/
│   │   ├── citizen-charter.md                # Timelines, processing windows, income limits
│   │   └── acceptable-proofs.json            # Alternative documents lookup
│   └── receipts/
│       └── acknowledgement-slip.html         # Dynamic receipt with KL-EDIST-2026-XXXX tracking ID
│
├── cloud_navigator.py                        # PART 2: Cloud Navigation & Discovery Agent
│   ├── Service intent classifier
│   ├── Headless Playwright DOM Inspector & Schema Extractor
│   ├── Pro-forma discovery & auto-downloader
│   ├── Doubt-Clearing RAG engine (zero PII passed to cloud)
│   └── Hand-Off Serializer -> writes `current_form_schema.json` upon "Let's start filling"
│
├── local_form_filler.py                      # PART 3: Local Private Form-Filling Agent
│   ├── Form structure readback engine (offline TTS for blind / visual cards for deaf)
│   ├── Conversational multi-slot extractor (unstructured speech / signs -> structured fields)
│   ├── Playwright headless DOM injector
│   ├── Critic Agent (format validation regex & completeness guardrail)
│   ├── Supervisor Agent (Human-in-the-loop: voice "Submit" / Thumbs-up gesture)
│   └── Ephemeral Memory Purge (secure buffer overwrite on completion)
│
├── document_scanner.py                       # Vision & Spatial Guidance Module
│   ├── OpenCV contour & boundary stability tracker
│   ├── Sharpness evaluator (>85% Laplacian variance)
│   ├── Spatial directional voice prompts ("Move left 5cm", "Hold steady")
│   ├── Auto-snapshot & manual voice override ("Capture now")
│   └── Local OCR (Tesseract text & 12-digit Aadhaar extraction)
│
├── vision_gesture_engine.py                  # Citizen Sign & Gesture Recognition Engine
│   ├── MediaPipe Hand tracking & ROI bounding box evaluator (using sign/translate pose normalization)
│   ├── Citizen sign interpreter (fingerspelling, number signs, and intent tokens)
│   └── Gesture classifier (Thumbs-up = Confirm / Submit, Open Palm = Cancel)
│
├── kiosk_hardware_sim.py                     # Hardware Sensor Fabric Simulator
│   ├── Voice wake detector ("Help me register")
│   ├── Screen triple-tap detector (<700ms)
│   ├── Ultrasonic proximity sensor & wheelchair height adapter
│   └── 10-second departure inactivity watchdog
│
├── tests/                                    # Standalone Module Tests
│   ├── test_module1_portal.py
│   ├── test_module2_cloud_nav.py
│   ├── test_module3_vision_ocr.py
│   ├── test_module4_accessibility.py
│   ├── test_module5_dom_injection.py
│   └── test_module6_governance_purge.py
│
├── test_assets/                              # Test Documents & Fixtures
│   ├── generate_test_id.py                   # Script generating realistic Aadhaar test card image
│   └── sample_aadhaar_card.png               # Synthesized ID card with photo, name, and 12-digit UID
│
├── run_omnikiosk_demo.py                     # PART 4: Unified End-to-End Demonstration Script
└── requirements.txt                          # Python dependencies
```

---

## 3. In-Depth Technical Specification of the 6 Decoupled Modules

To facilitate team distribution, isolated development, and granular debugging, the system is decomposed into **6 independent working modules**. Each module has explicit internal workflows, input/output data contracts, failure modes, and a dedicated test runner.

---

### MODULE 1: Civic Service Web Portal & Document Host (`mock_edistrict`)

#### 1. Core Responsibilities & Inner Architecture
Module 1 implements the official civic portal (**Mock e-District Kerala**) running as an asynchronous HTTP service on `http://localhost:3000`. It serves semantic HTML5 forms, legal pro-forma downloads, knowledge base resources, dynamic receipts, and the accessibility UI dock.

* **Asynchronous Web Service (`server.py`):**
  - Serves static assets (`/static/css/`, `/static/js/`), forms (`/forms/`), downloadable documents (`/docs/`), and knowledge base policies (`/kb/`).
  - Handles `POST /api/submit-application` with multipart form data parsing (text inputs and uploaded file binary blobs).
  - Generates dynamic receipts under `/receipts/acknowledgement-slip.html` with unique tracking tokens and timestamps.
* **Form Schemas with Exact Required Selectors:**
  1. `forms/income-certificate.html`:
     - `#txtApplicantName` (`input[type="text"][required]`)
     - `#txtAadhaarNo` (`input[type="text"][pattern="[0-9]{12}"][required]`)
     - `#ddlDistrict` (`select[required]`: Thiruvananthapuram, Ernakulam, Kozhikode, Thrissur, Kannur)
     - `#ddlTaluk` (`select[required]`: Dynamically populated based on selected district)
     - `#ddlVillage` (`select[required]`: Dynamically populated based on selected taluk)
     - `#txtRationCardNo` (`input[type="text"][required]`)
     - `#txtAnnualIncome` (`input[type="number"][min="1"][required]`)
     - `#ddlPurpose` (`select[required]`: Higher Education, Scholarship, Housing Scheme, General)
     - `#fileAadhaar` (`input[type="file"][accept=".pdf,.png,.jpg"][required]`)
     - `#btnSubmit` (`button[type="submit"]`)
  2. `forms/disability-pension.html`:
     - `#applicantName`, `#aadhaarNo`, `#disabilityCategory`, `#disabilityPercent` (min="40"), `#bankAccountNo`, `#ifscCode`.
  3. `forms/community-certificate.html`:
     - `#applicantName`, `#aadhaarNo`, `#ddlReligion`, `#ddlCaste`, `#fileCasteProof`.
* **Dynamic Cascading Dropdowns (`portal.js`):**
  - Event listener on `#ddlDistrict` change clears and injects relevant `<option>` nodes into `#ddlTaluk`.
  - Event listener on `#ddlTaluk` change populates corresponding `#ddlVillage` offices.
* **On-Screen Accessibility Trigger (`kiosk_ui.js`):**
  - Header button `#btnSignLanguage` (*"Start Sign Language Input"*): Dispatches a custom DOM event `kiosk:start-sign-language` and switches stylesheet to `/static/css/high_contrast.css`.
* **Downloadable Legal Pro-formas (`/docs/`):**
  - `self-declaration-affidavit.pdf`: Printable income pro-forma for informal workers.
  - `medical-board-assessment.pdf`: Disability assessment certificate.
* **Knowledge Base Documents (`/kb/`):**
  - `citizen-charter.md`: Income eligibility limits (Rs. 1,00,000/yr for scholarships), validity (1 year), and 7-day SLA.
  - `acceptable-proofs.json`: Fallback proof mappings (e.g. self-declaration if pay slip unavailable).
* **Dynamic Receipt Generation (`/receipts/acknowledgement-slip.html`):**
  - Renders tracking number `KL-EDIST-2026-XXXX` (where `XXXX` is a random 4-digit token).
  - Renders submission timestamp, receiving Village Office, and dynamic SVG barcode & QR code.

#### 2. Input / Output Data Contracts
* **Input:** HTTP GET requests for HTML/CSS/PDF/MD assets; HTTP POST requests with form fields and uploaded file blob.
* **Output:** HTTP 200 responses with valid HTML5 semantics; JSON `{ "status": "SUCCESS", "tracking_id": "KL-EDIST-2026-XXXX", "receipt_url": "/receipts/acknowledgement-slip.html?id=KL-EDIST-2026-XXXX" }`.

#### 3. Standalone Verification (`tests/test_module1_portal.py`)
* Boots the portal web server on port 3000 in a background process.
* Sends HTTP GET requests to `/forms/income-certificate.html`, `/forms/disability-pension.html`, `/docs/self-declaration-affidavit.pdf`, and `/kb/citizen-charter.md`. Asserts 200 OK.
* Inspects HTML DOM to verify that every required ID (`#txtApplicantName`, `#txtAadhaarNo`, `#btnSignLanguage`, etc.) exists and has correct validation attributes.
* Submits a test multipart POST request; asserts that response navigates to receipt with valid `KL-EDIST-2026-\d{4}` tracking token.

---

### MODULE 2: Cloud Navigator, Document Discovery & Doubt-Clearing (`cloud_navigator.py`)

#### 1. Core Responsibilities & Inner Architecture
Module 2 is the public discovery layer. It operates prior to citizen data entry and executes with zero citizen PII exposure.

```
 [ User Spoken/Sign Intent ] ──► [ Intent Classifier ] ──► Target Service URL
                                                              │
                                                              ▼
 [ Playwright Headless Browser ] ◄────────────────────────────┘
         │
         ├─► [ DOM Schema Extractor ] ──► Discovers IDs, types, selects, upload requirements
         ├─► [ Pro-forma Downloader ] ──► Detects affidavit needs -> downloads from /docs/
         └─► [ RAG Doubt-Clearing ]   ──► Ingests /kb/ -> Plain-language 2-sentence answers
                                                              │
 [ Hand-Off Trigger: "Let's start filling" ] ─────────────────┘
         │
         ▼
 [ Writes `current_form_schema.json` & Terminates Cloud Session ]
```

* **Natural Language Intent Resolver:**
  - Ingests citizen intent (e.g., *"I need an income certificate for college admission"*).
  - Matches intent against route registry and resolves URL: `http://localhost:3000/forms/income-certificate.html`.
* **Playwright Headless DOM Schema Extractor:**
  - Launches headless Chromium via Playwright, navigates to the resolved URL, and inspects the live page.
  - Queries all form inputs (`input, select, textarea, button`).
  - Serializes each field: `id`, `name`, `type`, `required`, `pattern`, `min`, `max`, and dropdown options into an abstract schema.
* **Pro-forma Discovery & Auto-Downloader:**
  - Scrapes the page for file upload instructions. Detects references to required affidavits or medical certificates.
  - Downloads the corresponding template from `http://localhost:3000/docs/self-declaration-affidavit.pdf` to `./downloads/`.
  - Notifies user via text card / TTS that a pro-forma template is available.
* **RAG Doubt-Clearing Engine (Strict PII Stripper):**
  - Ingests `/kb/citizen-charter.md` and `/kb/acceptable-proofs.json`.
  - When citizen asks an informational question (e.g. *"What counts as annual income?"*):
    1. **PII Sanitizer:** Runs regex filters removing any names, phone numbers, Aadhaar numbers, or dates.
    2. **Retrieval:** Fetches the relevant excerpt from the knowledge base.
    3. **Cloud LLM Call (Groq / Gemini API with local fallback):** Generates a simplified, 6th-grade reading level explanation strictly under 2 sentences.
    4. **Display:** Returns plain text rendered on on-screen visual cards or spoken via TTS.
* **Hand-Off Serializer:**
  - Monitors for hand-off trigger phrases (*"Let's start filling"*, *"Start form"*, *"Begin"*).
  - Serializes the extracted form schema into `current_form_schema.json`.
  - Cleanly severs all external cloud network connections before private data entry begins.

#### 2. Input / Output Data Contracts
* **Input:** Natural language query string (e.g., *"I need an income certificate"*).
* **Output:** `current_form_schema.json` containing:
  ```json
  {
    "service_name": "Income Certificate",
    "form_url": "http://localhost:3000/forms/income-certificate.html",
    "fields": [
      { "id": "txtApplicantName", "type": "text", "required": true, "label": "Full Name" },
      { "id": "txtAadhaarNo", "type": "text", "pattern": "[0-9]{12}", "required": true, "label": "Aadhaar UID" },
      { "id": "ddlDistrict", "type": "select", "options": ["Thiruvananthapuram", "Ernakulam", "Kozhikode"], "required": true },
      { "id": "ddlTaluk", "type": "select", "required": true },
      { "id": "ddlVillage", "type": "select", "required": true },
      { "id": "txtRationCardNo", "type": "text", "required": true },
      { "id": "txtAnnualIncome", "type": "number", "min": "1", "required": true },
      { "id": "ddlPurpose", "type": "select", "options": ["Higher Education", "Scholarship", "Housing Scheme", "General"], "required": true },
      { "id": "fileAadhaar", "type": "file", "accept": ".pdf,.png,.jpg", "required": true }
    ],
    "downloaded_docs": ["downloads/self-declaration-affidavit.pdf"]
  }
  ```

#### 3. Standalone Verification (`tests/test_module2_cloud_nav.py`)
* Executes `cloud_navigator.py` with intent *"I need an income certificate for college"*.
* Asserts that Playwright navigates to `http://localhost:3000/forms/income-certificate.html`.
* Asserts that all form elements (text inputs, selects, file upload) are extracted into `current_form_schema.json`.
* Asserts that `self-declaration-affidavit.pdf` is downloaded to `./downloads/`.
* Sends doubt query *"What counts as annual income?"*; asserts response is grounded, concise (<=2 sentences), and contains zero PII.
* Triggers *"Let's start filling"*; asserts hand-off JSON is created and cloud session is closed.

---

### MODULE 3: Document Computer Vision Scanner & Spatial Guidance (`document_scanner.py`)

#### 1. Core Responsibilities & Inner Architecture
Module 3 assists citizens (especially blind or visually impaired visitors) in positioning and capturing physical ID cards and paper documents under the kiosk camera.

```
 [ Video Stream (60 FPS) ] ──► [ OpenCV Grayscale + Gaussian Blur ]
                                             │
                                             ▼
 [ Canny Edge Detection ] ──► [ Find Contours (Area > 20% of frame) ]
                                             │
                                             ▼
 [ Polygon Approximation (approxPolyDP) ] ──► Quadrilateral Bounding Box
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [ Spatial Vector Math ]                    [ Sharpness Evaluator ]
          ΔX, ΔY offsets from frame center            Laplacian Variance: Var(∇²I)
          Skew Angle: atan2(dy, dx)                   Sharpness Threshold > 85%
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
               [ Active Spatial Voice Prompts: "Move left 5cm", "Hold steady" ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          Stability > 15 frames + Sharpness > 85%         Voice Trigger: "Capture now"
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                              [ Auto-Snapshot High-Res Frame ]
                                             │
                                             ▼
                              [ Local On-Device Tesseract OCR ]
                              Extracts: 12-digit Aadhaar UID, Name, DOB
```

* **OpenCV Contour Tracing & Rectangular Detection:**
  - Converts incoming video frame to grayscale; applies Gaussian blur ($5 \times 5$).
  - Computes Canny edges (thresholds 50 and 150), followed by morphological closing to bridge contour gaps.
  - Detects contours using `cv2.findContours(..., cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`.
  - Filters candidate contours by minimum bounding area ($>20\%$ of frame area) to eliminate visual noise.
  - Approximates contours using `cv2.approxPolyDP` (epsilon $= 0.02 \times \text{perimeter}$) to locate 4-corner polygons.
* **Spatial Alignment Vector Engine:**
  - Calculates document center $(C_x, C_y)$ relative to camera frame center $(W/2, H/2)$:
    $$\Delta X = C_x - \frac{W}{2}, \quad \Delta Y = C_y - \frac{H}{2}$$
  - Computes skew angle $\theta = \arctan2(y_2 - y_1, x_2 - x_1)$ along the top document edge.
* **Active Spatial Voice Guidance Generator:**
  - If $|\Delta X| > 40\text{px}$: Emits directional cue (*"Move the document 5cm to your left"* or *"Move right"*).
  - If $|\Delta Y| > 40\text{px}$: Emits vertical cue (*"Move document up"* or *"Move document down"*).
  - If $|\theta| > 5^\circ$: Emits rotation cue (*"Rotate paper slightly clockwise"*).
  - If aligned: Emits *"Hold steady. Capturing now."*
* **Sharpness Thresholding & Auto-Snapshot:**
  - Evaluates image sharpness using the Laplacian variance operator:
    $$\text{Sharpness} = \text{Var}(\nabla^2 I)$$
  - Requires sharpness $>85\%$ of the pre-calibrated clear-frame baseline.
  - Auto-triggers snapshot when bounding box coordinates remain stable ($\pm 5\text{px}$) across 15 consecutive frames.
  - **Manual Voice Override:** Immediate snapshot triggered upon detecting the spoken phrase *"Capture now"*.
* **Local On-Device OCR (Tesseract / Regex Extractor):**
  - Runs Tesseract OCR locally on the snapped cropped quadrilateral image.
  - Extracts:
    - **12-digit Aadhaar Number:** via regex `\b\d{4}\s?\d{4}\s?\d{4}\b`.
    - **Full Name:** via biographical label matching (`Name:`, `DOB:`, or top text block).
  - Keeps image in volatile memory as an in-memory byte buffer (zero disk writes).

#### 2. Input / Output Data Contracts
* **Input:** Video frame stream (from webcam device `/dev/video0` or automated test frame generator).
* **Output:** Snapped frame buffer in RAM + structured JSON:
  ```json
  {
    "status": "CAPTURED",
    "extracted_data": {
      "full_name": "Arun Kumar",
      "aadhaar_number": "987654321098",
      "dob": "1994-05-15"
    },
    "image_buffer": "<bytes object in volatile memory>",
    "sharpness_score": 92.4
  }
  ```

#### 3. Standalone Verification (`tests/test_module3_vision_ocr.py`)
* Feeds synthetic test video frames:
  1. Frame 1 (Shifted 100px right): Asserts guidance output equals *"Move document left"*.
  2. Frame 2 (Rotated 15 degrees): Asserts guidance output equals *"Rotate paper"*.
  3. Frame 3 (Blurry frame): Asserts sharpness $<85\%$ and capture is held.
  4. Frame 4 (Centered, sharp Aadhaar card image): Asserts auto-snapshot triggers.
* Verifies local OCR extracts Name *"Arun Kumar"* and Aadhaar *"987654321098"*.
* Tests voice override trigger *"Capture now"* forcing immediate capture.

---

### MODULE 4: Accessibility Trigger Fabric, Citizen Sign Input & Hardware Sim (`accessibility_engine.py` & `vision_gesture_engine.py`)

#### 1. Core Responsibilities & Inner Architecture
Module 4 manages the physical and interactive accessibility modes for blind, deaf, non-verbal, and wheelchair-bound citizens.

```
                                [ CITIZEN INTERACTION ]
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
 [ Voice Wake Event ]             [ #btnSignLanguage ]              [ Ultrasonic Sensor ]
 ("Help me register")             OR [ Screen Triple-Tap ]          Citizen Height Polling
         │                                 │                                 │
         ▼                                 ▼                                 ▼
 [ Privacy Screen Dim 0% ]        [ High-Contrast Visual UI ]       [ Wheelchair Detected ]
 Prevents bystander snooping       Pure black & high-vis yellow      Altitude < 135cm
 Contextual directional TTS        Top camera + MediaPipe active     Canvas -> Lower 33%
                                           │                                 │
                                           ▼                                 ▼
                                  [ Citizen Sign Input ]            [ 10-Second Watchdog ]
                                  Fingerspelling & Gestures:        Distance > 150cm for 10s
                                  - Thumbs-up: Confirm/Submit       -> Security Abort Purge
                                  - Open-palm: Cancel
```

* **Voice-Wake Pipeline (Blind / Low-Vision Mode):**
  - Offline listener detects the conversational wake phrase *"Help me register"*.
  - **Privacy Mode:** Dispatches a signal dimming the kiosk display to 0% brightness or rendering an opaque privacy screen ("Terminal in Private Audio Session") to prevent bystanders from viewing sensitive personal data.
  - Engages directional Text-to-Speech (TTS) delivering spoken prompts directly to the citizen.
* **On-Screen Sign Language Trigger & Triple-Tap Listener:**
  - Detects click on `#btnSignLanguage` or 3 rapid pointer taps (<700ms) anywhere on the touchscreen.
  - Activates **High-Contrast Theme** (`#000000` background, `#FFE600` primary text, `#00E5FF` interactive accents).
  - Renders large, high-visibility visual display cards for all instructions and doubt-clearing answers.
* **Citizen Sign Language & Gesture Recognition Pipeline (Adapted from `sign/translate`):**
  - Activates top camera and runs MediaPipe Hands tracking 21 3D landmarks per hand.
  - **Pose Normalization:** Leverages `sign/translate`'s coordinate normalization (`normalizePose`) relative to shoulder width and wrist reference points so recognition is scale and distance invariant.
  - **Citizen Input Interpretation:**
    - Detects static fingerspelled letters and number signs (0–9) for entering names and numbers.
    - Recognizes control gestures:
      * **Thumbs-Up:** Triggers confirmation / form submission.
      * **Open Palm:** Triggers cancellation / form reset.
  - **Kiosk Feedback:** The kiosk displays clean, instant visual text cards and banners (no complex 3D avatar rendering needed).
* **Ultrasonic Proximity & Wheelchair Height Adaptation:**
  - Continuously polls citizen distance and altitude.
  - If approaching citizen altitude is $<135\text{cm}$ (or wheelchair detected), injects CSS rules anchoring all interactive UI cards, form viewports, and touch buttons to the **lower third (bottom 33%) of the display**.
* **Departure Inactivity Watchdog:**
  - Ultrasonic sensor detects when citizen distance exceeds 150cm (user walked away).
  - Initiates a 10-second security countdown abort timer. If user does not return within 10 seconds, triggers an immediate emergency volatile memory purge.

#### 2. Input / Output Data Contracts
* **Input:** Raw audio PCM stream, touch tap coordinates and timestamps, ultrasonic distance/height metrics, camera video stream.
* **Output:** State event notifications:
  ```json
  {
    "active_mode": "DEAF_SIGN_MODE",
    "screen_theme": "HIGH_CONTRAST_DARK",
    "canvas_position": "LOWER_THIRD",
    "recognized_gesture": "THUMBS_UP",
    "gesture_confidence": 0.94
  }
  ```

#### 3. Standalone Verification (`tests/test_module4_accessibility.py`)
* Simulates voice wake *"Help me register"*; asserts screen brightness drops to 0% / privacy shield activates.
* Simulates `#btnSignLanguage` click and 3 rapid taps (<700ms); asserts high-contrast theme and gesture engine activate.
* Feeds hand landmark coordinates for Thumbs-Up; asserts gesture classifier returns `"THUMBS_UP"` with confidence $>90\%$.
* Simulates ultrasonic height $= 110\text{cm}$; asserts layout shifts to lower third.
* Simulates user departure (distance $>150\text{cm}$ for 10s); asserts 10-second security abort event fires.

---

### MODULE 5: Local Form-Filling Engine & Step-by-Step Intake (`local_form_filler.py`)

#### 1. Core Responsibilities & Inner Architecture
Module 5 is the private on-device execution engine. It ingests the form schema from Module 2, the document data from Module 3, and conversational speech/signs from the user, autonomously populating the live civic portal.

```
 [ current_form_schema.json ] ──► [ Local Form Filling Controller ]
                                                 │
 ┌───────────────────────────────────────────────┴───────────────────────────────────────────────┐
 │ STEP-BY-STEP MULTIMODAL READBACK                                                              │
 │ • Blind Mode: Offline TTS reads next field ("Please state your annual family income")         │
 │ • Deaf Mode: High-contrast visual card highlights the active input field                      │
 └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                 │
                                                 ▼
 [ Citizen Input: Spoken Statement OR Fingerspelled Sign Tokens ]
                                                 │
                                                 ▼
 [ Local Edge SLM (Conversational Slot Extractor) ]
 Parses unstructured statement into structured parameters:
 "My name is Arun Kumar, income is 75000, purpose is Scholarship"
 -> { "txtApplicantName": "Arun Kumar", "txtAnnualIncome": 75000, "ddlPurpose": "Scholarship" }
                                                 │
                                                 ▼
 [ Autonomous Playwright DOM Injector ]
 • Navigates to target form on http://localhost:3000
 • Types text into #txtApplicantName, #txtAadhaarNo, #txtRationCardNo, #txtAnnualIncome
 • Handles cascading dropdowns: Selects District -> waits for Taluk -> selects Village
 • Injects in-memory document snapshot buffer directly into #fileAadhaar
```

* **Step-by-Step Field Readback Engine:**
  - Iterates through required fields in `current_form_schema.json`.
  - Prompts citizen field by field:
    * Blind Mode: Speaks contextual prompt via local TTS (*"What is your annual family income?"*).
    * Deaf Mode: Displays prominent high-contrast prompt card on screen.
* **Conversational Multi-Slot Extractor (Local Edge SLM):**
  - Citizens rarely speak in single-word answers. They say: *"My name is Arun Kumar, my ration card number is 2451098, and my annual family income is 75000 rupees for my college scholarship."*
  - An on-device quantized model (or deterministic multi-entity regex slot extractor) extracts multiple slots in a single turn.
  - Merges extracted voice slots with biographical OCR attributes (Aadhaar number and Name from Module 3).
* **Autonomous Playwright DOM Injector:**
  - Connects to the active Chromium browser session on `http://localhost:3000`.
  - Injects values into corresponding DOM elements using `page.fill(selector, value)`.
  - Dispatches standard HTML5 `input` and `change` events so frontend validation and reactive frameworks recognize the input.
  - **Cascading Dropdown Handling:**
    1. Selects `#ddlDistrict` with value `"Thiruvananthapuram"`.
    2. Awaits `#ddlTaluk` options population; selects `"Neyyattinkara"`.
    3. Awaits `#ddlVillage` options population; selects `"Nemom"`.
  - **In-Memory File Upload:**
    * Directly injects the document image buffer from Module 3 into `#fileAadhaar` using Playwright's `set_input_files` API via an in-memory buffer representation, guaranteeing zero persistent disk writes.

#### 2. Input / Output Data Contracts
* **Input:** `current_form_schema.json`, document OCR payload, spoken transcript / sign tokens.
* **Output:** Fully populated live DOM state on `http://localhost:3000/forms/income-certificate.html`.

#### 3. Standalone Verification (`tests/test_module5_dom_injection.py`)
* Ingests a mock `current_form_schema.json` and sample OCR data.
* Feeds conversational statement *"My annual income is 85000 and purpose is Higher Education"*.
* Executes Playwright injection into `http://localhost:3000/forms/income-certificate.html`.
* Queries live DOM: Asserts `#txtApplicantName` has value `"Arun Kumar"`, `#txtAadhaarNo` has `"987654321098"`, `#txtAnnualIncome` has `"85000"`, cascading dropdowns are populated, and `#fileAadhaar` has the attached image buffer.

---

### MODULE 6: Multi-Agent Governance (Critic & Supervisor) & Ephemeral RAM Purge (`governance_and_purge.py`)

#### 1. Core Responsibilities & Inner Architecture
Module 6 provides pre-submission verification guardrails, enforces biometric human-in-the-loop confirmation, submits the application, captures the receipt tracking number, and performs cryptographic memory zeroization.

```
 [ Populated Form DOM State ] ──► [ CRITIC AGENT (Pre-Submission Audit) ]
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
       [ Syntax Regex Checks ]                                       [ Discrepancy Checks ]
       - Aadhaar: ^\d{12}$                                           - Compares Spoken Name vs
       - Income: > 0                                                   OCR Document Name
       - Mandatory files attached                                    - Flags inconsistencies
                 │                                                             │
                 └──────────────────────────────┬──────────────────────────────┘
                                                │ ALL CHECKS PASS
                                                ▼
                                [ SUPERVISOR AGENT (Interlock Gate) ]
                                Holds execution lock on form submit button
                                Generates multimodal pre-submit summary:
                                - Blind: Directional TTS spoken summary
                                - Deaf: High-contrast visual review card
                                                │
                                                ▼
                                [ Biometric Confirmation Signal ]
                                Spoken "Confirm" / "Submit" OR Thumbs-Up Gesture
                                                │
                                                ▼
                                [ Issue Execution Token & Click #btnSubmit ]
                                                │
                                                ▼
                                [ Verify Navigation & Parse Receipt ID ]
                                URL: /receipts/acknowledgement-slip.html
                                Scrapes Tracking ID: `KL-EDIST-2026-XXXX`
                                                │
                                                ▼
                                [ ZERO-TRACE EPHEMERAL PURGE ]
                                • `sodium_memzero()` overwrites RAM buffers
                                • Browser context terminated; /dev/shm cleared
                                • System resets to initial wake state
```

* **Critic Agent (Pre-Submission Form Verification Guardrail):**
  - Inspects all populated DOM values prior to user confirmation.
  - **Syntax Validation:**
    * Aadhaar Number: Validates exactly 12 digits via `^\d{12}$` and Verhoeff/Luhn checksum algorithm.
    * Annual Income: Validates positive numeric value $> 0$.
    * Mandatory Dropdowns: Validates `#ddlDistrict`, `#ddlTaluk`, `#ddlVillage` are selected and not on placeholder indexes.
    * Mandatory File Attachment: Asserts file input has a valid attached buffer.
  - **Discrepancy Detection:** Compares the applicant name spoken by the user against the name extracted from the physical document OCR. If Levenshtein edit distance exceeds threshold, pauses execution and alerts the user.
* **Supervisor Agent (Human-in-the-Loop Circuit Breaker):**
  - The automated browser agent is architecturally blocked from triggering the final HTTP POST/Submit event on its own.
  - Generates a multimodal summary of all entered information:
    * Blind Mode: Speaks full audio summary via directional TTS: *"Please verify: Name Arun Kumar, Aadhaar ending in 1098, Annual income 85000 rupees. Say 'Submit' to send your application."*
    * Deaf Mode: Displays a full-screen high-contrast verification card and prompts for a Thumbs-Up gesture.
  - **Confirmation Gate:** Listens for explicit spoken confirmation (*"Submit"*, *"Confirm"*) or verified MediaPipe Thumbs-Up gesture held for $>1\text{s}$.
* **Form Submission & Receipt Tracking:**
  - Upon valid confirmation, clicks `#btnSubmit`.
  - Verifies navigation to `http://localhost:3000/receipts/acknowledgement-slip.html`.
  - Scrapes and captures the generated Application Tracking ID (`KL-EDIST-2026-XXXX`) and submission timestamp.
* **Ephemeral Memory Flush (Zero-Trace Purge):**
  - Overwrites all camera frame buffers, audio buffers, OCR strings, and user profile data in memory with random/zero bytes (`sodium_memzero` / secure zeroization).
  - Terminates the Playwright browser incognito session, purging `/dev/shm` shared memory segments.
  - Resets UI to initial idle wake state, ensuring zero citizen data persists in memory or on disk.

#### 2. Input / Output Data Contracts
* **Input:** Populated DOM state on port 3000, confirmation signal (spoken "Submit" or Thumbs-up gesture).
* **Output:** Verified receipt tracking number (`KL-EDIST-2026-XXXX`) + verified zeroed memory state.

#### 3. Standalone Verification (`tests/test_module6_governance_purge.py`)
* Tests Critic Agent:
  - Injects invalid 10-digit Aadhaar: Asserts Critic flags syntax error and halts.
  - Injects valid 12-digit Aadhaar and data: Asserts Critic passes.
* Tests Supervisor Interlock:
  - Asserts form submit is blocked without confirmation.
  - Sends Thumbs-Up confirmation: Asserts submission proceeds.
* Asserts page navigates to receipt and extracts `KL-EDIST-2026-\d{4}` tracking token.
* Asserts memory purge function executes and verifies internal buffer is cleared to `None` / `0x00`.

---

## 4. End-to-End Unified Integration Workflow (`run_omnikiosk_demo.py`)

In addition to the 6 standalone test runners, `run_omnikiosk_demo.py` integrates all 6 modules into an automated end-to-end demonstration representing the full citizen journey:

```
 Step 1: Boot Mock Portal on port 3000 (Module 1)
 Step 2: User intent "I need an income certificate" -> Discover & extract schema (Module 2)
 Step 3: User doubt "What counts as income?" -> RAG answers without PII (Module 2)
 Step 4: Hand-off trigger "Let's start filling" -> Writes schema & exits cloud (Module 2)
 Step 5: Accessibility trigger -> High-contrast mode / wheelchair adaptation (Module 4)
 Step 6: OpenCV spatial guidance -> Align document, snap & OCR Aadhaar (Module 3)
 Step 7: Step-by-step intake -> Playwright injects personal data & document (Module 5)
 Step 8: Critic Agent validates syntax -> Supervisor confirms via Thumbs-up (Module 6)
 Step 9: Form submitted -> Dynamic receipt KL-EDIST-2026-XXXX captured (Module 6)
 Step 10: Ephemeral RAM purge -> Zero trace left in memory (Module 6)
```

### Complete Verification Test Suite Commands

```bash
# Test each module in total isolation:
python3 tests/test_module1_portal.py
python3 tests/test_module2_cloud_nav.py
python3 tests/test_module3_vision_ocr.py
python3 tests/test_module4_accessibility.py
python3 tests/test_module5_dom_injection.py
python3 tests/test_module6_governance_purge.py

# Run the complete end-to-end integrated demo:
python3 run_omnikiosk_demo.py
```
