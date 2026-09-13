from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_liveness_check_does_not_require_database(self):
        response = self.client.get("/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_check_reports_database_available(self):
        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "checks": {"database": "ok"}})

    @patch("clinic.health.connection.cursor", side_effect=OperationalError)
    def test_readiness_check_reports_database_unavailable(self, mock_cursor):
        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "checks": {"database": "unavailable"}},
        )
        mock_cursor.assert_called_once()
