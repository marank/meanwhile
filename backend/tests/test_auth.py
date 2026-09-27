def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "display_name": "Alice", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["access_token"]

    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 200

    r = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "bad"},
    )
    assert r.status_code == 401


def test_protected_routes_require_auth(client):
    assert client.get("/api/users/me").status_code == 401


def test_first_user_is_admin_and_later_users_are_not(user_factory):
    first = user_factory("first@example.com")
    second = user_factory("second@example.com")
    assert first["is_admin"] is True
    assert second["is_admin"] is False


def test_login_rate_limited_after_repeated_failures(client, user_factory):
    user_factory("ratelimit@example.com")
    for _ in range(10):
        r = client.post(
            "/api/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrong-password"},
        )
        assert r.status_code == 401

    # Even the correct password is refused while the limit is active.
    r = client.post(
        "/api/auth/login",
        json={"email": "ratelimit@example.com", "password": "password123"},
    )
    assert r.status_code == 429


def test_login_rate_limit_does_not_lock_out_other_users(client, user_factory):
    user_factory("rl-victim@example.com")
    for _ in range(10):
        client.post(
            "/api/auth/login",
            json={"email": "rl-attacker@example.com", "password": "wrong"},
        )
    r = client.post(
        "/api/auth/login",
        json={"email": "rl-victim@example.com", "password": "password123"},
    )
    assert r.status_code == 200
