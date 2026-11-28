"""Admin dashboard lists keep their wrappers while adding pagination metadata."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CompanyProfile, User


class AdminPaginationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", is_staff=True
        )
        active_user = User.objects.create_user(
            email="active@example.com", password="pass12345"
        )
        CompanyProfile.objects.create(
            user=active_user,
            organisation_name="Active Co",
            classification="private",
            country="IN",
            cin_number="CIN-ACTIVE",
            status=CompanyProfile.STATUS_ACTIVE,
        )
        self.pending_user = User.objects.create_user(
            email="pending@example.com", password="pass12345"
        )
        CompanyProfile.objects.create(
            user=self.pending_user,
            organisation_name="Pending Co",
            classification="private",
            country="IN",
            cin_number="CIN-PENDING",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_entities_list_keeps_counts_and_adds_pagination(self):
        response = self.client.get("/api/auth/admin/entities/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["counts"]["active"], 1)
        self.assertIsInstance(response.data["entities"], list)
        self.assertEqual(len(response.data["entities"]), 1)

    def test_verification_queue_keeps_pending_count_and_adds_pagination(self):
        response = self.client.get("/api/auth/admin/verification-queue/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["pending_count"], 1)
        self.assertIsInstance(response.data["requests"], list)
        self.assertEqual(len(response.data["requests"]), 1)

    def test_verification_queue_exposes_email_verified_status(self):
        response = self.client.get("/api/auth/admin/verification-queue/")

        self.assertFalse(response.data["requests"][0]["email_verified"])

        self.pending_user.email_verified = True
        self.pending_user.save(update_fields=["email_verified"])

        response = self.client.get("/api/auth/admin/verification-queue/")

        self.assertTrue(response.data["requests"][0]["email_verified"])
