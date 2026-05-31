import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["FREERADIUS_SHARED_SECRET"] = "radius-test-secret"
os.environ["PAYMENT_WEBHOOK_SECRET"] = "payment-test-secret"
os.environ["SATELLITE_API_KEY"] = "satellite-test-key"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


def login():
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@jaguar.local", "password": "ChangeMeNow!2026"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_and_admin_login():
    assert client.get("/api/health").json()["name"] == "JAGUAR TECHNOLOGIES"
    assert login()


def test_subscriber_can_be_authorized_by_radius():
    token = login()
    plans = client.get("/api/plans").json()
    subscriber = {
        "account_no": "JT-1001",
        "name": "Pilot Customer",
        "phone": "+15550001001",
        "email": "pilot@example.com",
        "radius_username": "pilot1001",
        "radius_password": "strong-pass-1001",
        "plan_id": plans[0]["id"],
    }
    created = client.post(
        "/api/subscribers",
        json=subscriber,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 200, created.text
    response = client.post(
        "/api/radius/authorize",
        json={"username": "pilot1001", "password": "strong-pass-1001", "nas_ip_address": "10.0.0.1"},
        headers={"X-Radius-Secret": "radius-test-secret"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allow"] is True
    assert body["radius_group"] == plans[0]["radius_group"]


def test_radius_rejects_bad_secret():
    response = client.post(
        "/api/radius/authorize",
        json={"username": "nobody", "password": "bad"},
        headers={"X-Radius-Secret": "wrong"},
    )
    assert response.status_code == 401
