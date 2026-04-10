from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import TEST_OPERATOR_PASSWORDS, extract_csrf_token, login_as


def test_login_success_and_logout(client: TestClient) -> None:
    login_as(client, "reviewer")

    operator_page = client.get("/operator/exceptions")
    assert operator_page.status_code == 200
    assert "reviewer" in operator_page.text

    csrf_token = extract_csrf_token(operator_page.text)
    logout = client.post(
        "/operator/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert logout.status_code == 303
    assert logout.headers["location"] == "/operator/login?message=Logged%20out."

    redirected = client.get("/operator/exceptions", follow_redirects=False)
    assert redirected.status_code == 303
    assert redirected.headers["location"] == "/operator/login?next=/operator/exceptions"


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    login_page = client.get("/operator/login")
    csrf_token = extract_csrf_token(login_page.text)

    response = client.post(
        "/operator/login",
        data={
            "username": "reviewer",
            "password": "wrong-password",
            "csrf_token": csrf_token,
            "next": "/operator/exceptions",
        },
    )

    assert response.status_code == 401
    assert "Invalid username or password." in response.text


def test_login_rejects_invalid_csrf_token(client: TestClient) -> None:
    response = client.post(
        "/operator/login",
        data={
            "username": "reviewer",
            "password": TEST_OPERATOR_PASSWORDS["reviewer"],
            "csrf_token": "bad-token",
            "next": "/operator/exceptions",
        },
    )

    assert response.status_code == 403
    assert "Invalid CSRF token." in response.text


def test_operator_pages_redirect_to_login_when_unauthenticated(client: TestClient) -> None:
    response = client.get("/operator/exceptions", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/operator/login?next=/operator/exceptions"


def test_json_review_routes_require_authentication(client: TestClient) -> None:
    list_response = client.get("/exceptions")
    detail_response = client.get("/exceptions/missing-case")
    approve_response = client.post("/exceptions/missing-case/approve", json={"reason": "x"})

    assert list_response.status_code == 401
    assert list_response.json()["detail"] == "auth_required"
    assert detail_response.status_code == 401
    assert detail_response.json()["detail"] == "auth_required"
    assert approve_response.status_code == 401
    assert approve_response.json()["detail"] == "auth_required"


def test_json_approval_routes_require_approver_role(client: TestClient) -> None:
    login_as(client, "reviewer")

    response = client.post("/exceptions/missing-case/approve", json={"reason": "x"})

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_role"
