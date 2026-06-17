"""Tests for app/api/v1/verified.py — ownership transfer, care instructions, vaccination alerts."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.models import (
    User, Pet, Subscription, OwnershipTransfer,
    VaccinationAlert, VaccinationDocument, _utc_now,
)
from app.api.v1.routes import serializer


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(client, test_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


@pytest.fixture
def verified_user(session, test_user):
    """Give test_user a verified subscription."""
    sub = Subscription(
        user_id=test_user.id,
        stripe_customer_id="cus_verified",
        stripe_subscription_id="sub_verified",
        tier="verified",
        status="active",
        current_period_start=_utc_now(),
        current_period_end=_utc_now() + timedelta(days=365),
    )
    session.add(sub)
    session.commit()
    return test_user


@pytest.fixture
def verified_client(client, verified_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(verified_user.id)))
    return client


@pytest.fixture
def other_user(session):
    user = User(sub="other_sub", email="other@example.com", name="Other User")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def other_client(session, other_user):
    def get_session_override():
        return session
    from app.main import fastapi_app
    from app.database import get_session
    fastapi_app.dependency_overrides[get_session] = get_session_override
    c = TestClient(fastapi_app)
    c.cookies.set("paws_user_id", serializer.dumps(str(other_user.id)))
    yield c


# ═══════════════════════════════════════════════════════════════
# OWNERSHIP TRANSFER
# ═══════════════════════════════════════════════════════════════

class TestOwnershipTransfer:

    def test_initiate_transfer(self, verified_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "newowner@example.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "transfer_token" in data
        assert data["expires_in"] == "7 days"

    def test_initiate_transfer_to_self_rejected(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "test@example.com"},
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"]

    def test_initiate_transfer_invalid_email(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_initiate_transfer_requires_verified_tier(self, authenticated_client, test_pet):
        resp = authenticated_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "newowner@example.com"},
        )
        assert resp.status_code == 403

    def test_initiate_transfer_requires_ownership(self, verified_client, session):
        other = User(sub="stranger", email="stranger@x.com", name="Stranger")
        session.add(other)
        session.flush()
        alien_pet = Pet(name="Alien", chip_id="999000000000001", owner_id=other.id)
        session.add(alien_pet)
        session.commit()

        resp = verified_client.post(
            f"/api/v1/pets/{alien_pet.id}/transfer",
            json={"new_owner_email": "someone@example.com"},
        )
        assert resp.status_code == 403

    def test_duplicate_pending_transfer_rejected(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        # First transfer
        verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "first@example.com"},
        )
        # Second transfer should fail
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "second@example.com"},
        )
        assert resp.status_code == 409
        assert "pending" in resp.json()["detail"]

    def test_accept_transfer(self, verified_client, test_pet, session, other_user, other_client, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        # Initiate transfer to other_user
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": other_user.email},
        )
        token = resp.json()["transfer_token"]

        # Accept as other_user
        resp = other_client.post(
            "/api/v1/transfer/accept",
            json={"transfer_token": token},
        )
        assert resp.status_code == 200
        assert test_pet.name in resp.json()["message"]

        session.refresh(test_pet)
        assert test_pet.owner_id == other_user.id

    def test_accept_transfer_wrong_email(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "someone.else@example.com"},
        )
        token = resp.json()["transfer_token"]

        # Try accepting as the original owner (wrong email)
        resp = verified_client.post(
            "/api/v1/transfer/accept",
            json={"transfer_token": token},
        )
        assert resp.status_code == 403
        assert "different email" in resp.json()["detail"]

    def test_accept_transfer_expired(self, verified_client, test_pet, session, other_user, other_client, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": other_user.email},
        )
        token = resp.json()["transfer_token"]

        # Manually expire the transfer
        from sqlmodel import select
        transfer = session.exec(
            select(OwnershipTransfer).where(OwnershipTransfer.transfer_token == token)
        ).first()
        transfer.initiated_at = _utc_now() - timedelta(days=8)
        session.add(transfer)
        session.commit()

        resp = other_client.post(
            "/api/v1/transfer/accept",
            json={"transfer_token": token},
        )
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"]

    def test_accept_transfer_already_accepted(self, verified_client, test_pet, session, other_user, other_client, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": other_user.email},
        )
        token = resp.json()["transfer_token"]

        # Accept once
        other_client.post("/api/v1/transfer/accept", json={"transfer_token": token})

        # Try again
        resp = other_client.post("/api/v1/transfer/accept", json={"transfer_token": token})
        assert resp.status_code == 409

    def test_transfer_details_public(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "viewer@example.com"},
        )
        token = resp.json()["transfer_token"]

        # Unauthenticated client can see details
        from fastapi.testclient import TestClient
        from app.main import fastapi_app
        unauth_client = TestClient(fastapi_app)
        resp = unauth_client.get(f"/api/v1/transfer/details?token={token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pet_name"] == test_pet.name
        assert data["status"] == "pending"
        assert data["is_expired"] is False

    def test_transfer_details_not_found(self, client):
        resp = client.get(f"/api/v1/transfer/details?token={uuid4()}")
        assert resp.status_code == 404

    def test_transfer_history(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "history@example.com"},
        )

        resp = verified_client.get(f"/api/v1/pets/{test_pet.id}/transfer-history")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["to_email"] == "history@example.com"

    def test_cancel_transfer(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "cancel_target@example.com"},
        )
        assert resp.status_code == 200

        # Cancel the pending transfer
        resp = verified_client.post(f"/api/v1/pets/{test_pet.id}/transfer/cancel")
        assert resp.status_code == 200
        assert "canceled" in resp.json()["message"].lower()

        # Verify it's actually canceled
        from sqlmodel import select
        transfer = session.exec(
            select(OwnershipTransfer).where(
                OwnershipTransfer.pet_id == test_pet.id,
                OwnershipTransfer.to_owner_email == "cancel_target@example.com",
            )
        ).first()
        assert transfer.status == "canceled"

    def test_cancel_transfer_no_pending(self, verified_client, test_pet):
        resp = verified_client.post(f"/api/v1/pets/{test_pet.id}/transfer/cancel")
        assert resp.status_code == 404
        assert "No pending" in resp.json()["detail"]

    def test_cancel_transfer_allows_new_transfer(self, verified_client, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        # Initiate and cancel
        verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "first@example.com"},
        )
        verified_client.post(f"/api/v1/pets/{test_pet.id}/transfer/cancel")

        # Should be able to initiate a new one
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/transfer",
            json={"new_owner_email": "second@example.com"},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# CARE INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════

class TestCareInstructions:

    def test_get_care_instructions(self, verified_client, test_pet):
        resp = verified_client.get(f"/api/v1/pets/{test_pet.id}/care-instructions")
        assert resp.status_code == 200
        data = resp.json()
        assert "energy_level" in data
        assert "feeds_per_day" in data
        assert "dietary_notes" in data

    def test_update_care_instructions(self, verified_client, test_pet):
        resp = verified_client.put(
            f"/api/v1/pets/{test_pet.id}/care-instructions",
            json={
                "energy_level": "High",
                "feeds_per_day": 3,
                "dietary_notes": "No chicken — allergic",
                "exercise_needs": "30 min walk twice daily",
                "temperament": "Friendly with kids",
                "care_notes": "Loves belly rubs",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["energy_level"] == "High"
        assert data["feeds_per_day"] == 3
        assert data["dietary_notes"] == "No chicken — allergic"
        assert data["exercise_needs"] == "30 min walk twice daily"

    def test_update_care_partial(self, verified_client, test_pet):
        resp = verified_client.put(
            f"/api/v1/pets/{test_pet.id}/care-instructions",
            json={"medical_conditions": "Arthritis in left hip"},
        )
        assert resp.status_code == 200
        assert resp.json()["medical_conditions"] == "Arthritis in left hip"

    def test_care_instructions_require_verified(self, authenticated_client, test_pet):
        resp = authenticated_client.get(
            f"/api/v1/pets/{test_pet.id}/care-instructions",
        )
        assert resp.status_code == 403

    def test_care_instructions_require_ownership(self, verified_client, session):
        other = User(sub="ci_other", email="ci_other@x.com", name="CI Other")
        session.add(other)
        session.flush()
        other_pet = Pet(name="NotMine", chip_id="999000000000002", owner_id=other.id)
        session.add(other_pet)
        session.commit()

        resp = verified_client.get(f"/api/v1/pets/{other_pet.id}/care-instructions")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# VACCINATION ALERTS
# ═══════════════════════════════════════════════════════════════

class TestVaccinationAlerts:

    def test_create_alert(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/alerts",
            json={
                "title": "Rabies booster due",
                "alert_date": "2027-03-15",
                "description": "Annual rabies vaccination",
                "alert_type": "vaccination_expiry",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Rabies booster due"
        assert data["alert_date"] == "2027-03-15"

    def test_create_alert_invalid_date(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/alerts",
            json={
                "title": "Test",
                "alert_date": "not-a-date",
            },
        )
        assert resp.status_code == 422

    def test_list_alerts(self, verified_client, test_pet, session, test_user):
        for i in range(3):
            session.add(VaccinationAlert(
                pet_id=test_pet.id, user_id=test_user.id,
                title=f"Alert {i}",
                alert_date=_utc_now() + timedelta(days=i * 30),
            ))
        session.commit()

        resp = verified_client.get(f"/api/v1/pets/{test_pet.id}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be sorted by date ascending
        dates = [item["alert_date"] for item in data]
        assert dates == sorted(dates)

    def test_delete_alert(self, verified_client, test_pet, session, test_user):
        alert = VaccinationAlert(
            pet_id=test_pet.id, user_id=test_user.id,
            title="Delete me", alert_date=_utc_now(),
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)

        resp = verified_client.delete(f"/api/v1/pets/{test_pet.id}/alerts/{alert.id}")
        assert resp.status_code == 200

        resp = verified_client.get(f"/api/v1/pets/{test_pet.id}/alerts")
        assert len(resp.json()) == 0

    def test_delete_alert_not_found(self, verified_client, test_pet):
        resp = verified_client.delete(f"/api/v1/pets/{test_pet.id}/alerts/{uuid4()}")
        assert resp.status_code == 404

    def test_alerts_require_verified(self, authenticated_client, test_pet):
        resp = authenticated_client.get(f"/api/v1/pets/{test_pet.id}/alerts")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# VACCINATION DOCUMENT UPLOAD
# ═══════════════════════════════════════════════════════════════

class TestVaccinationUpload:

    @patch("app.api.v1.verified.R2StorageService")
    def test_upload_pdf(self, mock_r2, verified_client, test_pet):
        mock_r2.upload_vaccination_doc.return_value = "https://files.pawsledger.com/vacc/test.pdf"

        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("vaccine.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_upload_invalid_type(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("malware.exe", b"MZ evil", "application/x-msdownload")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    def test_upload_too_large(self, verified_client, test_pet):
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("big.pdf", large_content, "application/pdf")},
        )
        assert resp.status_code == 400
        assert "10MB" in resp.json()["detail"]

    @patch("app.api.v1.verified.R2StorageService")
    def test_upload_r2_failure(self, mock_r2, verified_client, test_pet):
        mock_r2.upload_vaccination_doc.return_value = None

        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("doc.pdf", b"%PDF content", "application/pdf")},
        )
        assert resp.status_code == 500

    def test_upload_requires_verified(self, authenticated_client, test_pet):
        resp = authenticated_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("doc.pdf", b"%PDF content", "application/pdf")},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# CONTACT UPDATE REMINDERS
# ═══════════════════════════════════════════════════════════════

class TestContactReminders:

    @patch.dict("os.environ", {"CRON_SECRET": "test-secret"})
    def test_reminders_require_cron_secret(self, client):
        resp = client.post(
            "/api/v1/subscription/send-update-reminders",
            headers={"x-cron-secret": "wrong"},
        )
        assert resp.status_code == 403

    @patch.dict("os.environ", {"CRON_SECRET": "test-secret"})
    def test_reminders_sent_to_eligible_users(self, client, session, test_user, mocker):
        mock_email = mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_remind",
            tier="verified",
            status="active",
        )
        session.add(sub)
        session.commit()

        resp = client.post(
            "/api/v1/subscription/send-update-reminders",
            headers={"x-cron-secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert "1 users" in resp.json()["message"]
        mock_email.assert_called_once()

    @patch.dict("os.environ", {"CRON_SECRET": "test-secret"})
    def test_reminders_skipped_if_recently_reminded(self, client, session, test_user, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        test_user.contact_reminded_at = _utc_now() - timedelta(days=30)
        session.add(test_user)
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_skip",
            tier="verified",
            status="active",
        )
        session.add(sub)
        session.commit()

        resp = client.post(
            "/api/v1/subscription/send-update-reminders",
            headers={"x-cron-secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert "0 users" in resp.json()["message"]
        assert "1 skipped" in resp.json()["message"]

    @patch.dict("os.environ", {"CRON_SECRET": "test-secret"})
    def test_reminders_skipped_if_profile_recently_updated(self, client, session, test_user, mocker):
        mocker.patch(
            "app.api.v1.verified.email_service.send_email",
            new_callable=AsyncMock,
        )
        test_user.profile_updated_at = _utc_now() - timedelta(days=10)
        session.add(test_user)
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_updated",
            tier="verified",
            status="active",
        )
        session.add(sub)
        session.commit()

        resp = client.post(
            "/api/v1/subscription/send-update-reminders",
            headers={"x-cron-secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert "0 users" in resp.json()["message"]


# ═══════════════════════════════════════════════════════════════
# VACCINATION DOCUMENT UPLOAD
# ═══════════════════════════════════════════════════════════════

class TestVaccinationDocumentUpload:

    def test_upload_requires_verified_tier(self, authenticated_client, test_pet):
        resp = authenticated_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert resp.status_code == 403

    def test_upload_succeeds_for_verified(self, verified_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.verified.R2StorageService.upload_vaccination_doc",
            return_value="https://r2.example.com/vaccinations/test/abc.pdf",
        )
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Document uploaded successfully."
        assert "id" in data

    def test_upload_rejects_invalid_file_type(self, verified_client, test_pet):
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("script.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    def test_upload_enforces_verified_tier_limit(self, verified_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.verified.R2StorageService.upload_vaccination_doc",
            return_value="https://r2.example.com/vaccinations/test/abc.pdf",
        )
        # Upload first doc (should succeed)
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report1.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        assert resp.status_code == 200

        # Upload second doc (should fail — verified limit is 1)
        resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report2.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "limit reached" in resp.json()["detail"].lower()

    def test_list_documents(self, verified_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.verified.R2StorageService.upload_vaccination_doc",
            return_value="https://r2.example.com/vaccinations/test/abc.pdf",
        )
        # Upload one
        verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        # List
        resp = verified_client.get(
            f"/api/v1/pets/{test_pet.id}/vaccinations/documents",
        )
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "report.pdf"

    def test_delete_document(self, verified_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.verified.R2StorageService.upload_vaccination_doc",
            return_value="https://r2.example.com/vaccinations/test/abc.pdf",
        )
        mocker.patch(
            "app.api.v1.verified.R2StorageService.delete_file",
            return_value=True,
        )
        # Upload
        upload_resp = verified_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        doc_id = upload_resp.json()["id"]

        # Delete
        resp = verified_client.delete(
            f"/api/v1/pets/{test_pet.id}/vaccinations/documents/{doc_id}",
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify list is now empty
        list_resp = verified_client.get(
            f"/api/v1/pets/{test_pet.id}/vaccinations/documents",
        )
        assert len(list_resp.json()) == 0
