import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as breachcheck 

client = breachcheck.app.test_client()


class FakeResponse:

    def __init__(self, status_code, data=None, text=""):
        self.status_code = status_code
        self.data = data
        self.text = text

    def json(self):
        return self.data


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert b"breachcheck" in response.data


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_security_headers():
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_secret_page_is_never_cached():
    response = client.get("/secret/abc12345")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_password_prefix_must_be_5_hex_characters():
    response = client.get("/api/password/hello")
    assert response.status_code == 400


def test_password_check_reads_counts(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(200, text="1E4C9B93F3F0682250B6CF8331B7EE68FD8:52000\nABC:0")

    monkeypatch.setattr(breachcheck.requests, "get", fake_get)
    response = client.get("/api/password/5BAA6")
    results = response.get_json()["results"]
    assert results["1E4C9B93F3F0682250B6CF8331B7EE68FD8"] == 52000


def test_breaches_are_cached(monkeypatch):
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return FakeResponse(200, data=[{
            "Title": "Canva", "Domain": "canva.com", "BreachDate": "2019-05-24",
            "AddedDate": "2019-05-27T23:01:51Z", "PwnCount": 137000000, "DataClasses": ["Passwords"], "IsVerified": True,
        }])

    monkeypatch.setattr(breachcheck.requests, "get", fake_get)
    breachcheck.cache["breaches"] = None
    breachcheck.cache["saved_at"] = 0

    first = client.get("/api/breaches").get_json()
    second = client.get("/api/breaches").get_json()

    assert first["source"] == "api"
    assert second["source"] == "cache"
    assert len(calls) == 1


def test_spam_lists_are_skipped(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(200, data=[
            {"Title": "Canva", "Domain": "canva.com", "BreachDate": "2019-05-24",
             "AddedDate": "2019-05-27T23:01:51Z", "PwnCount": 137000000,
             "DataClasses": ["Passwords"], "IsVerified": True},
            {"Title": "Spam List", "Domain": "", "BreachDate": "2020-01-01",
             "AddedDate": "2020-01-02T00:00:00Z", "PwnCount": 5000,
             "DataClasses": ["Email addresses"], "IsVerified": False, "IsSpamList": True},
        ])

    monkeypatch.setattr(breachcheck.requests, "get", fake_get)
    breachcheck.cache["breaches"] = None
    breachcheck.cache["saved_at"] = 0

    data = client.get("/api/breaches").get_json()
    assert len(data["breaches"]) == 1
    assert data["breaches"][0]["added"] == "2019-05-27"


def test_breaches_api_down_returns_503(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(500)

    monkeypatch.setattr(breachcheck.requests, "get", fake_get)
    breachcheck.cache["breaches"] = None
    breachcheck.cache["saved_at"] = 0

    response = client.get("/api/breaches")
    assert response.status_code == 503


def test_share_rejects_empty_secret(monkeypatch):
    monkeypatch.setattr(breachcheck, "ots_username", "test")
    monkeypatch.setattr(breachcheck, "ots_api_key", "test")
    response = client.post("/api/share", json={"secret": "", "ttl": 3600})
    assert response.status_code == 400


def test_share_rejects_bad_expiry(monkeypatch):
    monkeypatch.setattr(breachcheck, "ots_username", "test")
    monkeypatch.setattr(breachcheck, "ots_api_key", "test")
    response = client.post("/api/share", json={"secret": "hi", "ttl": 5})
    assert response.status_code == 400


def test_share_rejects_more_than_7_days(monkeypatch):
    monkeypatch.setattr(breachcheck, "ots_username", "test")
    monkeypatch.setattr(breachcheck, "ots_api_key", "test")
    response = client.post("/api/share", json={"secret": "hi", "ttl": 8 * 86400})
    assert response.status_code == 400


def test_share_accepts_custom_minutes(monkeypatch):
    sent = {}

    def fake_post(url, auth, data, timeout):
        sent["ttl"] = data["ttl"]
        return FakeResponse(200, data={"secret_key": "abc12345", "metadata_key": "def67890"})

    monkeypatch.setattr(breachcheck, "ots_username", "test")
    monkeypatch.setattr(breachcheck, "ots_api_key", "test")
    monkeypatch.setattr(breachcheck.requests, "post", fake_post)
    # 45 minutes = 2700 seconds
    response = client.post("/api/share", json={"secret": "hi", "ttl": 2700})
    assert response.status_code == 200
    assert sent["ttl"] == 2700


def test_reveal_rejects_bad_key():
    response = client.post("/api/reveal/<script>")
    assert response.status_code in (400, 404)


def test_reveal_already_viewed(monkeypatch):
    def fake_post(url, auth, timeout):
        return FakeResponse(404)

    monkeypatch.setattr(breachcheck, "ots_username", "test")
    monkeypatch.setattr(breachcheck, "ots_api_key", "test")
    monkeypatch.setattr(breachcheck.requests, "post", fake_post)
    response = client.post("/api/reveal/abc12345")
    assert response.status_code == 404
    assert "already viewed" in response.get_json()["error"]

