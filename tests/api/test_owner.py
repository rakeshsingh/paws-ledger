"""Tests for app/api/v1/owner.py — owner profile view and update."""

import pytest
from app.models import User
from app.api.v1.routes import serializer


@pytest.fixture
def authenticated_client(client, test_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


class TestOwnerProfile:

    def test_get_owner_profile(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/owner/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_user.name
        assert data["email"] == test_user.email
        assert "phone" in data
        assert "city" in data
        assert "country" in data
        assert "pet_count" in data

    def test_get_owner_profile_unauthenticated(self, client):
        response = client.get("/api/v1/owner/profile")
        assert response.status_code == 401

    def test_update_owner_profile_full(self, authenticated_client):
        payload = {
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone": "+1-555-123-4567",
            "address": "123 Main St, Portland, OR",
            "city": "Portland",
            "country": "United States",
        }
        response = authenticated_client.put("/api/v1/owner/profile", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "updated@example.com"
        assert data["phone"] == "+1-555-123-4567"
        assert data["city"] == "Portland"
        assert data["country"] == "United States"

    def test_update_owner_profile_partial(self, authenticated_client, test_user):
        response = authenticated_client.put(
            "/api/v1/owner/profile", json={"city": "Seattle"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Seattle"
        assert data["name"] == test_user.name

    def test_update_owner_address(self, authenticated_client):
        payload = {"address": "456 Oak Ave, Seattle, WA"}
        response = authenticated_client.put("/api/v1/owner/profile/address", json=payload)
        assert response.status_code == 200
        assert response.json()["address"] == "456 Oak Ave, Seattle, WA"

    def test_update_email_duplicate_rejected(self, authenticated_client, session):
        other_user = User(sub="other-sub", email="taken@example.com", name="Other")
        session.add(other_user)
        session.commit()

        response = authenticated_client.put(
            "/api/v1/owner/profile", json={"email": "taken@example.com"}
        )
        assert response.status_code == 409

    def test_update_email_invalid_format_rejected(self, authenticated_client):
        response = authenticated_client.put(
            "/api/v1/owner/profile", json={"email": "not-an-email"}
        )
        assert response.status_code == 422

    def test_update_name_empty_rejected(self, authenticated_client):
        response = authenticated_client.put(
            "/api/v1/owner/profile", json={"name": "   "}
        )
        assert response.status_code == 422
