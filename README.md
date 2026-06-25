# VI Matrix – Intelligent Crowd Analysis System

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-REST%20API-green)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Object%20Detection-orange)
![CI](https://github.com/Ipshita0906/vi-matrix/actions/workflows/test.yml/badge.svg)

A full-stack crowd intelligence platform that uses YOLOv8 object detection and statistical density estimation to analyze real-time crowd behaviour, detect anomalies, and stream live metrics to a web dashboard.

---

## Features

- **Real-time crowd analysis** — YOLOv8-powered object detection with sub-200ms inference latency
- **Anomaly detection** — probabilistic density thresholding for behavioural event detection
- **Live dashboard** — RESTful Flask API streams crowd metrics, alerts, and analytics over HTTP
- **Secure multi-user auth** — registration with 6-digit OTP email verification, hashed passwords, timed password reset tokens via `itsdangerous`
- **14+ REST endpoints** — fully protected with a custom `login_required` decorator
- **CI/CD pipeline** — GitHub Actions automatically runs pytest suite on every commit

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Computer Vision | YOLOv8, OpenCV |
| Auth & Security | Werkzeug (password hashing), itsdangerous (tokens), Flask-Mail (OTP) |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Testing | pytest |
| CI/CD | GitHub Actions |

---

## Project Structure

```
vi-matrix/
├── .github/
│   └── workflows/
│       └── test.yml        # CI pipeline
├── templates/
│   └── index.html          # Dashboard frontend
├── static/                 # CSS, JS assets
├── app.py                  # Flask backend (14+ REST endpoints)
├── test_app.py             # pytest suite (20 tests)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/Ipshita0906/vi-matrix.git
cd vi-matrix
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your actual values
```

### 4. Run the app
```bash
python app.py
# Visit http://localhost:5000
```

---

## Running Tests

```bash
pytest test_app.py -v
```

Tests cover: registration, OTP verification, login/logout, all protected routes (401 checks), analytics endpoint structure, and password reset flow.

---

## API Endpoints

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| POST | `/api/register` | No | Register new user |
| POST | `/api/verify` | No | Verify account with OTP |
| POST | `/login` | No | Login |
| GET | `/logout` | No | Logout |
| GET | `/api/devices` | Yes | List all cameras |
| GET | `/api/alerts` | Yes | Get all system alerts |
| GET | `/api/analytics/crowd_density` | Yes | Crowd density over time |
| GET | `/api/analytics/peak_density` | Yes | Peak density by zone |
| GET | `/api/analytics/footfall` | Yes | Footfall by hour |
| GET | `/api/analytics/behavior_events` | Yes | Behavioural events (7 days) |
| GET | `/api/analytics/emotion_pie` | Yes | Emotion breakdown |
| GET | `/api/analytics/aggression_panic` | Yes | Aggression vs panic events |
| POST | `/api/request-password-reset` | No | Request reset email |
| POST | `/api/reset-with-token` | No | Reset password with token |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
SECRET_KEY=your-secret-key
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
DATABASE_FILE=users.db
```

> Never commit your `.env` file. It is in `.gitignore`.

---

## Built By

Ipshita Maheshwari — [LinkedIn](https://www.linkedin.com/in/ipshita-maheshwari-56426230a)
