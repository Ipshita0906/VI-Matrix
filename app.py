import os
import random
import threading
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    Response,
    url_for
)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import yolo_processor

# Load .env file if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Database Setup ---
DATABASE_FILE = os.environ.get('DATABASE_FILE', 'users.db')

def get_db_conn():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified INTEGER NOT NULL DEFAULT 0,
                verification_code TEXT
            );
        ''')
    conn.close()
    print("Database initialized.")

init_db()

# Start YOLOv8 background inference thread
VIDEO_PATH = os.environ.get('VIDEO_PATH', 'crowd.mp4')
yolo_processor.start(VIDEO_PATH)

# Mock device data
MOCK_DEVICES = [
    { 'id': 'cam-01', 'name': 'CAM-01: Main Entrance', 'status': 'Online', 'model': 'YOLOv8n-Crowd', 'ip': '192.168.1.101', 'uptime': '72h 14m' },
    { 'id': 'cam-02', 'name': 'CAM-02: Plaza', 'status': 'Online', 'model': 'YOLOv8m-Behavior', 'ip': '192.168.1.102', 'uptime': '72h 14m' },
    { 'id': 'cam-03', 'name': 'CAM-03: Restricted Zone A', 'status': 'Online', 'model': 'YOLOv8s-Intrusion', 'ip': '192.168.1.103', 'uptime': '6h 02m' },
    { 'id': 'cam-04', 'name': 'CAM-04: Exit Hall', 'status': 'Offline', 'model': 'YOLOv8n-Crowd', 'ip': '192.168.1.104', 'uptime': '0m' },
]

def _generate_mock_alerts(count=100):
    alerts = []
    severities = ['Critical', 'Warning', 'Info']
    types = ['Crowd Density', 'Intrusion', 'Behavior', 'Emotion']
    statuses = ['Acknowledged', 'New', 'New', 'New']
    for i in range(count):
        severity = random.choice(severities)
        alert_type = random.choice(types)
        camera = random.choice(MOCK_DEVICES)
        alerts.append({
            'id': f'A-{1024 + i}',
            'timestamp': (datetime.now() - timedelta(seconds=random.randint(0, 3600*72))).isoformat(),
            'severity': severity,
            'type': alert_type,
            'camera': camera['name'],
            'details': f'{alert_type} event detected at {camera["name"]}.',
            'status': random.choice(statuses)
        })
    alerts.sort(key=lambda x: x['timestamp'], reverse=True)
    return alerts

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def handle_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    conn = get_db_conn()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    if user is None:
        return jsonify({'success': False, 'message': 'Wrong email.'}), 200
    if check_password_hash(user['password_hash'], password):
        if user['is_verified'] == 0:
            return jsonify({'success': False, 'message': 'Account not verified.', 'not_verified': True})
        session['user'] = user['email']
        return jsonify({'success': True, 'message': 'Login successful'})
    return jsonify({'success': False, 'message': 'Wrong password.'}), 200

@app.route('/logout')
def handle_logout():
    session.pop('user', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/devices')
@login_required
def get_devices():
    return jsonify(MOCK_DEVICES)

@app.route('/api/alerts')
@login_required
def get_alerts():
    # Merge real YOLOv8 alerts with mock alerts
    real = yolo_processor.get_real_alerts()
    mock = _generate_mock_alerts(100)
    combined = real + mock
    combined.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(combined)

# --- Analytics: now powered by real YOLOv8 inference ---

@app.route('/api/analytics/crowd_density')
@login_required
def get_crowd_density():
    """Real person counts per frame from YOLOv8."""
    return jsonify(yolo_processor.get_crowd_density())

@app.route('/api/analytics/peak_density')
@login_required
def get_peak_density():
    """Peak density per zone derived from inference history."""
    return jsonify(yolo_processor.get_peak_density())

@app.route('/api/analytics/footfall')
@login_required
def get_footfall():
    """Real per-second average footfall from YOLOv8."""
    return jsonify(yolo_processor.get_footfall())

@app.route('/api/analytics/behavior_events')
@login_required
def get_behavior_events():
    return jsonify({'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'data': [2, 5, 3, 7, 4, 1, 3]})

@app.route('/api/analytics/emotion_pie')
@login_required
def get_emotion_pie():
    return jsonify({'labels': ['Neutral', 'Angry', 'Suspicious'], 'data': [82, 12, 6]})

@app.route('/api/analytics/aggression_panic')
@login_required
def get_aggression_panic():
    return jsonify({
        'labels': ['Entrance', 'Plaza', 'Zone A', 'Exit Hall'],
        'datasets': [
            { 'label': 'Aggression', 'data': [5, 2, 1, 0], 'backgroundColor': 'rgba(255, 99, 71, 0.3)', 'borderColor': '#ff6347' },
            { 'label': 'Panic', 'data': [1, 3, 0, 1], 'backgroundColor': 'rgba(0, 170, 255, 0.3)', 'borderColor': '#00aaff' }
        ]
    })

@app.route('/api/live_status')
@login_required
def get_live_status():
    """New endpoint: returns current inference status and live person count."""
    return jsonify(yolo_processor.get_latest_status())

@app.route('/api/setup_needed', methods=['GET'])
def is_setup_needed():
    conn = get_db_conn()
    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    return jsonify({'setup_needed': user_count == 0})

@app.route('/api/register', methods=['POST'])
def handle_register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400
    password_hash = generate_password_hash(password)
    verification_code = str(random.randint(100000, 999999))
    conn = get_db_conn()
    try:
        with conn:
            conn.execute(
                'INSERT INTO users (email, password_hash, verification_code, is_verified) VALUES (?, ?, ?, 0)',
                (email, password_hash, verification_code)
            )
        conn.close()
        try:
            msg = Message("Verify Your VI Matrix Account", recipients=[email],
                         body=f"Your verification code is: {verification_code}")
            mail.send(msg)
        except Exception as e:
            print(f"Mail error: {e}")
            return jsonify({'success': False, 'message': 'Account created but email failed.'}), 500
        return jsonify({'success': True, 'message': 'Account created. Check your email.'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Email already taken.'}), 400

@app.route('/api/verify', methods=['POST'])
def handle_verify():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    if not email or not code:
        return jsonify({'success': False, 'message': 'Email and code required.'}), 400
    conn = get_db_conn()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found.'}), 404
    if user['is_verified'] == 1:
        conn.close()
        return jsonify({'success': False, 'message': 'Already verified.'}), 400
    if user['verification_code'] == code:
        with conn:
            conn.execute('UPDATE users SET is_verified = 1, verification_code = NULL WHERE email = ?', (email,))
        conn.close()
        session['user'] = user['email']
        return jsonify({'success': True, 'message': 'Account verified!'})
    conn.close()
    return jsonify({'success': False, 'message': 'Invalid code.'}), 400

@app.route('/api/resend-code', methods=['POST'])
def resend_verification_code():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email required.'}), 400
    conn = get_db_conn()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if user is None:
        conn.close()
        return jsonify({'success': True, 'message': 'If account exists, code was sent.'})
    if user['is_verified'] == 1:
        conn.close()
        return jsonify({'success': False, 'message': 'Already verified.'}), 400
    new_code = str(random.randint(100000, 999999))
    with conn:
        conn.execute('UPDATE users SET verification_code = ? WHERE email = ?', (new_code, email))
    conn.close()
    try:
        msg = Message("New VI Matrix Verification Code", recipients=[email],
                     body=f"Your new code is: {new_code}")
        mail.send(msg)
    except Exception as e:
        print(f"Mail error: {e}")
        return jsonify({'success': False, 'message': 'Could not send email.'}), 500
    return jsonify({'success': True, 'message': 'New code sent.'})

@app.route('/api/request-password-reset', methods=['POST'])
def request_password_reset():
    data = request.json
    email = data.get('email')
    conn = get_db_conn()
    user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    if user is None:
        return jsonify({'success': True, 'message': 'If that email exists, a reset link has been sent.'})
    try:
        token = s.dumps(email, salt='password-reset-salt')
        reset_url = f"{request.host_url}#/reset/{token}"
        msg = Message("Password Reset - VI Matrix", recipients=[email],
                     body=f"Reset your password here:\n\n{reset_url}\n\nIgnore if not requested.")
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Reset link sent.'})
    except Exception as e:
        print(f"Mail error: {e}")
        return jsonify({'success': False, 'message': 'Could not send email.'}), 500

@app.route('/api/reset-with-token', methods=['POST'])
def reset_with_token():
    data = request.json
    token = data.get('token')
    new_password = data.get('password')
    if not token or not new_password:
        return jsonify({'success': False, 'message': 'Token and password required.'}), 400
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        return jsonify({'success': False, 'message': 'Token expired.'}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid token.'}), 400
    new_hash = generate_password_hash(new_password)
    conn = get_db_conn()
    with conn:
        conn.execute('UPDATE users SET password_hash = ? WHERE email = ?', (new_hash, email))
    conn.close()
    return jsonify({'success': True, 'message': 'Password reset successfully.'})

if __name__ == '__main__':
    app.run(debug=False, port=5000, threaded=True)