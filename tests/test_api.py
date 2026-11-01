import unittest

from fastapi.testclient import TestClient

from src.api import app
from src.storage import FreshBoxStore


class FreshBoxAPITests(unittest.TestCase):
    def setUp(self):
        self.store = FreshBoxStore(":memory:")
        app.state.store = self.store
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        del app.state.store
        self.store.close()

    def test_health_and_food_profile_crud(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["storage"], "sqlite")

        created = self.client.post(
            "/api/foods",
            json={
                "display_name": "Cucumber",
                "category": "vegetable",
                "profile": {"humidity": {"preferred_min_percent": None}},
            },
        )
        self.assertEqual(created.status_code, 201)
        food = created.json()

        listed = self.client.get("/api/foods?search=cuc")
        self.assertEqual(len(listed.json()), 1)

        updated = self.client.put(
            f"/api/foods/{food['food_id']}",
            json={"profile": {"temperature": {"preferred_max_c": None}}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["profile_version"], 2)

        missing = self.client.get("/api/foods/not-a-food")
        self.assertEqual(missing.status_code, 404)

    def test_batch_reading_observation_history_and_owner_association(self):
        food = self.client.post(
            "/api/foods",
            json={"display_name": "Apple", "category": "fruit"},
        ).json()
        batch_response = self.client.post(
            "/api/batches",
            json={
                "food_id": food["food_id"],
                "name": "First crate",
                "initial_weight_g": 800,
                "storage": {"location": "fridge"},
            },
        )
        self.assertEqual(batch_response.status_code, 201)
        batch = batch_response.json()

        start = self.client.post(f"/api/batches/{batch['batch_id']}/start")
        self.assertEqual(start.json()["status"], "monitoring")

        reading_response = self.client.post(
            "/api/sensors/readings",
            json={
                "batch_id": batch["batch_id"],
                "timestamp": "2020-10-27T06:00:00Z",
                "temperature_c": 4.5,
                "humidity_pct": 55,
                "gas_raw": 120,
                "weight_g": 795,
                "sensor_validity": {
                    "temperature": True,
                    "humidity": True,
                    "gas_raw": True,
                    "weight": True,
                },
                "device_status": "online",
                "device_id": "esp32-box-1",
                "idempotency_key": "test-reading-1",
            },
        )
        self.assertEqual(reading_response.status_code, 201)
        latest = self.client.get(
            f"/api/sensors/latest?batch_id={batch['batch_id']}"
        )
        self.assertEqual(
            latest.json()["latest_valid_reading_at"],
            "2020-10-27T06:00:00.000000+00:00",
        )
        self.assertEqual(latest.json()["device_status"], "stale")

        observation = self.client.post(
            f"/api/batches/{batch['batch_id']}/observations",
            json={
                "observation_source": "customer",
                "appearance": "firm",
                "verification_status": "unverified",
            },
        )
        self.assertEqual(observation.status_code, 201)
        history = self.client.get(f"/api/batches/{batch['batch_id']}/history")
        self.assertEqual(len(history.json()["readings"]), 1)
        self.assertEqual(len(history.json()["observations"]), 1)

        baseline_readings = []
        for index in range(5):
            response = self.client.post(
                "/api/sensors/readings",
                json={
                    "batch_id": batch["batch_id"],
                    "timestamp": f"2026-10-27T06:01:0{index}Z",
                    "temperature_c": 4.0 + index,
                    "sensor_validity": {"temperature": True},
                    "device_id": "esp32-box-1",
                },
            )
            self.assertEqual(response.status_code, 201)
            baseline_readings.append(response.json()["reading_id"])
        baseline = self.client.post(
            f"/api/batches/{batch['batch_id']}/baselines",
            json={
                "source_reading_ids": baseline_readings,
                "sensor_fields": ["temperature_c"],
                "algorithm_version": "mean-v1",
            },
        )
        self.assertEqual(baseline.status_code, 201)
        self.assertTrue(baseline.json()["reliable"])
        self.assertEqual(baseline.json()["values_json"]["temperature_c"], 6.0)

        wrong_batch = self.client.post(
            "/api/sensors/readings",
            json={
                "batch_id": "unknown-batch",
                "timestamp": "2026-10-27T06:00:01Z",
                "temperature_c": 20,
                "sensor_validity": {"temperature": True},
            },
        )
        self.assertEqual(wrong_batch.status_code, 404)

    def test_invalid_reading_duplicate_and_rsl_unavailable(self):
        food = self.client.post(
            "/api/foods",
            json={"display_name": "Potato", "category": "vegetable"},
        ).json()
        batch = self.client.post(
            "/api/batches",
            json={"food_id": food["food_id"]},
        ).json()

        invalid = self.client.post(
            "/api/sensors/readings",
            json={
                "batch_id": batch["batch_id"],
                "timestamp": "2026-10-27T06:00:00Z",
                "temperature_c": 100,
                "sensor_validity": {"temperature": True},
            },
        )
        self.assertEqual(invalid.status_code, 422)

        payload = {
            "batch_id": batch["batch_id"],
            "timestamp": "2026-10-27T06:00:00Z",
            "temperature_c": 4,
            "sensor_validity": {"temperature": True},
            "idempotency_key": "one-only",
        }
        first = self.client.post("/api/sensors/readings", json=payload)
        second = self.client.post("/api/sensors/readings", json=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

        assessment = self.client.get(
            f"/api/batches/{batch['batch_id']}/assessment"
        )
        self.assertFalse(assessment.json()["rsl_available"])


if __name__ == "__main__":
    unittest.main()
