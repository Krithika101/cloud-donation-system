import app as app_module
from app import app


def test_history_page_renders_for_logged_in_user():
    client = app.test_client()
    login_response = client.post(
        "/login",
        data={"email": "admin@donation.com", "password": "admin123"},
        follow_redirects=True,
    )

    assert login_response.status_code == 200

    history_response = client.get("/history")

    assert history_response.status_code == 200
    assert b"Donation History" in history_response.data


def test_donate_page_selects_cause_from_causes_link():
    client = app.test_client()
    login_response = client.post(
        "/login",
        data={"email": "admin@donation.com", "password": "admin123"},
        follow_redirects=True,
    )

    assert login_response.status_code == 200

    donate_response = client.get("/donate?cause_id=2")

    assert donate_response.status_code == 200
    assert b'value="2" selected' in donate_response.data


def test_causes_search_filters_results():
    client = app.test_client()
    response = client.get("/causes?search=food")

    assert response.status_code == 200
    assert b"Community Food Drive" in response.data
    assert b"Education Support" not in response.data


def test_admin_cannot_access_donation_form():
    client = app.test_client()
    login_response = client.post(
        "/login",
        data={"email": "admin@donation.com", "password": "admin123"},
        follow_redirects=True,
    )

    assert login_response.status_code == 200

    donation_response = client.get("/donate", follow_redirects=True)

    assert donation_response.status_code == 200
    assert b"Admin Dashboard" in donation_response.data
    assert b"Make a Donation" not in donation_response.data


def test_admin_can_add_cause_to_cloud_database(monkeypatch):
    inserted_cause = {}

    def save_cause(name, description, goal_amount):
        inserted_cause.update(
            name=name,
            description=description,
            goal_amount=goal_amount,
        )
        return "created"

    monkeypatch.setattr(app_module, "insert_cause", save_cause)
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user"] = {
            "email": "admin@donation.com",
            "name": "Admin User",
            "role": "admin",
        }

    response = client.post(
        "/admin/causes",
        data={
            "name": "Clean Water",
            "description": "Fund safe drinking water.",
            "goal_amount": "25000",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Cause added and saved to the cloud database." in response.data
    assert inserted_cause == {
        "name": "Clean Water",
        "description": "Fund safe drinking water.",
        "goal_amount": 25000.0,
    }


def test_donor_cannot_add_cause(monkeypatch):
    def fail_if_called(*_args):
        raise AssertionError("donor reached database insert")

    monkeypatch.setattr(app_module, "insert_cause", fail_if_called)
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user"] = {
            "email": "donor@example.com",
            "name": "Demo Donor",
            "role": "donor",
        }

    response = client.post(
        "/admin/causes",
        data={
            "name": "Unauthorized Cause",
            "description": "Should not be saved.",
            "goal_amount": "1000",
        },
    )

    assert response.status_code == 403
