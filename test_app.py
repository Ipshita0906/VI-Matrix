import pytest
import json
from unittest.mock import patch
from app import app, init_db, get_db_conn
import os
import tempfile

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with patch.dict(os.environ, {'DATABASE_FILE': db_path}):
        import app as app_module
        app_module.DATABASE_FILE = db_path
        init_db()
        with app.test_client() as client:
            yield client

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def registered_user(client):
    """Register and verify a test user, return credentials."""
    email = 'test@vimatrix.com'
    password = 'TestPass123!'

    # Register
    with patch('app.mail') as mock_mail:
        mock_mail.send.return_value = None
        client.post('/api/register', json={'email': email, 'password': password})

    # Get verification code directly from DB
    import app as app_module
    conn = get_db_conn()
    user = conn.execute('SELECT verification_code FROM users WHERE email = ?', (email,)).fetchone()
    code = user['verification_code']
    conn.close()

    # Verify account
    client.post('/api/verify', json={'email': email, 'code': code})

    return {'email': email, 'password': password}


@pytest.fixture
def logged_in_client(client, registered_user):
    """Return a client that is already logged in."""
    client.post('/login', json={
        'email': registered_user['email'],
        'password': registered_user['password']
    })
    return client


# ============================================================
# AUTH TESTS
# ============================================================

class TestRegistration:
    def test_register_new_user_success(self, client):
        """A new user can register successfully."""
        with patch('app.mail') as mock_mail:
            mock_mail.send.return_value = None
            res = client.post('/api/register', json={
                'email': 'new@test.com',
                'password': 'Password123!'
            })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data['success'] is True

    def test_register_duplicate_email_fails(self, client):
        """Registering with an existing email returns an error."""
        with patch('app.mail') as mock_mail:
            mock_mail.send.return_value = None
            client.post('/api/register', json={'email': 'dupe@test.com', 'password': 'Pass123!'})
            res = client.post('/api/register', json={'email': 'dupe@test.com', 'password': 'Pass123!'})
        assert res.status_code == 400
        data = json.loads(res.data)
        assert data['success'] is False

    def test_register_missing_fields_fails(self, client):
        """Registration without required fields returns an error."""
        res = client.post('/api/register', json={'email': 'incomplete@test.com'})
        assert res.status_code in [400, 200]
        data = json.loads(res.data)
        assert data['success'] is False


class TestVerification:
    def test_verify_with_correct_code(self, client):
        """User can verify account with correct OTP code."""
        with patch('app.mail') as mock_mail:
            mock_mail.send.return_value = None
            client.post('/api/register', json={'email': 'verify@test.com', 'password': 'Pass123!'})

        conn = get_db_conn()
        user = conn.execute('SELECT verification_code FROM users WHERE email = ?', ('verify@test.com',)).fetchone()
        code = user['verification_code']
        conn.close()

        res = client.post('/api/verify', json={'email': 'verify@test.com', 'code': code})
        data = json.loads(res.data)
        assert data['success'] is True

    def test_verify_with_wrong_code_fails(self, client):
        """Verification with wrong OTP code fails."""
        with patch('app.mail') as mock_mail:
            mock_mail.send.return_value = None
            client.post('/api/register', json={'email': 'wrongcode@test.com', 'password': 'Pass123!'})

        res = client.post('/api/verify', json={'email': 'wrongcode@test.com', 'code': '000000'})
        data = json.loads(res.data)
        assert data['success'] is False

    def test_verify_already_verified_fails(self, client, registered_user):
        """Verifying an already verified account returns error."""
        conn = get_db_conn()
        user = conn.execute('SELECT verification_code FROM users WHERE email = ?',
                          (registered_user['email'],)).fetchone()
        conn.close()

        res = client.post('/api/verify', json={
            'email': registered_user['email'],
            'code': '123456'
        })
        data = json.loads(res.data)
        assert data['success'] is False


class TestLogin:
    def test_login_with_valid_credentials(self, client, registered_user):
        """Verified user can log in successfully."""
        res = client.post('/login', json={
            'email': registered_user['email'],
            'password': registered_user['password']
        })
        data = json.loads(res.data)
        assert data['success'] is True

    def test_login_with_wrong_password_fails(self, client, registered_user):
        """Login with wrong password returns failure."""
        res = client.post('/login', json={
            'email': registered_user['email'],
            'password': 'WrongPassword!'
        })
        data = json.loads(res.data)
        assert data['success'] is False

    def test_login_with_nonexistent_email_fails(self, client):
        """Login with unregistered email returns failure."""
        res = client.post('/login', json={
            'email': 'nobody@test.com',
            'password': 'Pass123!'
        })
        data = json.loads(res.data)
        assert data['success'] is False

    def test_logout_clears_session(self, client, logged_in_client):
        """Logging out clears the user session."""
        res = logged_in_client.get('/logout')
        data = json.loads(res.data)
        assert data['success'] is True


# ============================================================
# PROTECTED ROUTE TESTS
# ============================================================

class TestProtectedRoutes:
    def test_devices_requires_login(self, client):
        """Unauthenticated request to /api/devices returns 401."""
        res = client.get('/api/devices')
        assert res.status_code == 401

    def test_alerts_requires_login(self, client):
        """Unauthenticated request to /api/alerts returns 401."""
        res = client.get('/api/alerts')
        assert res.status_code == 401

    def test_analytics_requires_login(self, client):
        """Unauthenticated request to analytics endpoints returns 401."""
        endpoints = [
            '/api/analytics/crowd_density',
            '/api/analytics/peak_density',
            '/api/analytics/footfall',
            '/api/analytics/behavior_events',
            '/api/analytics/emotion_pie',
            '/api/analytics/aggression_panic',
        ]
        for endpoint in endpoints:
            res = client.get(endpoint)
            assert res.status_code == 401, f"{endpoint} should require auth"

    def test_devices_accessible_when_logged_in(self, logged_in_client):
        """Authenticated user can access /api/devices."""
        res = logged_in_client.get('/api/devices')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_alerts_accessible_when_logged_in(self, logged_in_client):
        """Authenticated user can access /api/alerts."""
        res = logged_in_client.get('/api/alerts')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert isinstance(data, list)

    def test_alerts_have_required_fields(self, logged_in_client):
        """Each alert contains required fields."""
        res = logged_in_client.get('/api/alerts')
        data = json.loads(res.data)
        required_fields = ['id', 'timestamp', 'severity', 'type', 'camera', 'status']
        for alert in data[:5]:
            for field in required_fields:
                assert field in alert, f"Alert missing field: {field}"


# ============================================================
# ANALYTICS TESTS
# ============================================================

class TestAnalytics:
    def test_crowd_density_returns_correct_structure(self, logged_in_client):
        """Crowd density endpoint returns labels and data arrays."""
        res = logged_in_client.get('/api/analytics/crowd_density')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'labels' in data
        assert 'data' in data
        assert len(data['labels']) == len(data['data'])

    def test_footfall_returns_correct_structure(self, logged_in_client):
        """Footfall endpoint returns labels and data arrays."""
        res = logged_in_client.get('/api/analytics/footfall')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'labels' in data
        assert 'data' in data

    def test_emotion_pie_returns_correct_structure(self, logged_in_client):
        """Emotion pie endpoint returns labels and data arrays."""
        res = logged_in_client.get('/api/analytics/emotion_pie')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'labels' in data
        assert 'data' in data
        assert sum(data['data']) == 100

    def test_aggression_panic_returns_datasets(self, logged_in_client):
        """Aggression/panic endpoint returns multi-dataset structure."""
        res = logged_in_client.get('/api/analytics/aggression_panic')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'datasets' in data
        assert len(data['datasets']) == 2


# ============================================================
# PASSWORD RESET TESTS
# ============================================================

class TestPasswordReset:
    def test_reset_request_for_existing_user(self, client, registered_user):
        """Password reset request succeeds for existing user."""
        with patch('app.mail') as mock_mail:
            mock_mail.send.return_value = None
            res = client.post('/api/request-password-reset', json={
                'email': registered_user['email']
            })
        data = json.loads(res.data)
        assert data['success'] is True

    def test_reset_request_for_nonexistent_user(self, client):
        """Password reset for unknown email returns safe generic message."""
        res = client.post('/api/request-password-reset', json={
            'email': 'ghost@test.com'
        })
        data = json.loads(res.data)
        # Should not reveal whether email exists
        assert data['success'] is True

    def test_reset_with_invalid_token_fails(self, client):
        """Password reset with invalid token returns error."""
        res = client.post('/api/reset-with-token', json={
            'token': 'fake-invalid-token',
            'password': 'NewPass123!'
        })
        data = json.loads(res.data)
        assert data['success'] is False