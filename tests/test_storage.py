import tempfile
import unittest
from pathlib import Path

from src.storage import (
    ConflictError,
    FreshBoxStore,
    NotFoundError,
    ValidationError,
)


class FreshBoxStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = FreshBoxStore(":memory:")
        self.food = self.store.create_food_type(
            "Tomato",
            "vegetable",
            profile={"temperature": {"preferred_min_c": None}},
        )

    def tearDown(self):
        self.store.close()

    def make_batch(self, owner_id="alice"):
        return self.store.create_batch(
            self.food["food_id"],
            owner_id=owner_id,
            name="Kitchen batch",
            initial_weight_g=500,
            storage={"location": "counter"},
        )

    def make_reading(self, batch, index, **overrides):
        values = {
            "timestamp": f"2026-10-27T06:00:{index:02d}+00:00",
            "temperature_c": 22.5,
            "sensor_validity": {"temperature": True},
            "owner_id": batch["owner_id"],
            "device_id": "esp32-test",
        }
        values.update(overrides)
        return self.store.add_sensor_reading(batch["batch_id"], **values)

    def test_food_profile_update_preserves_versions(self):
        updated = self.store.update_food_profile(
            self.food["food_id"],
            {"humidity": {"preferred_min_percent": None}},
            provenance="customer-created",
        )

        self.assertEqual(updated["profile_version"], 2)
        self.assertEqual(updated["profile_json"], {
            "humidity": {"preferred_min_percent": None}
        })

        with self.store._connection() as connection:
            versions = connection.execute(
                "SELECT version FROM food_profiles WHERE food_id = ? ORDER BY version",
                (self.food["food_id"],),
            ).fetchall()
        self.assertEqual([row["version"] for row in versions], [1, 2])

    def test_batch_status_and_owner_isolation(self):
        batch = self.make_batch()

        self.assertEqual(batch["status"], "created")
        with self.assertRaises(NotFoundError):
            self.store.get_batch(batch["batch_id"], owner_id="bob")

        started = self.store.start_batch(
            batch["batch_id"],
            owner_id="alice",
            started_at="2026-10-27T06:01:00Z",
        )
        self.assertEqual(started["status"], "monitoring")
        completed = self.store.complete_batch(batch["batch_id"], owner_id="alice")
        self.assertEqual(completed["status"], "completed")

    def test_reading_is_preserved_and_duplicate_is_rejected(self):
        batch = self.make_batch()
        reading = self.make_reading(
            batch,
            1,
            idempotency_key="device-event-1",
            gas_raw=700,
            weight_g=492,
            calibration={"load_cell": "cal-v1"},
            data_source="physical_hardware",
        )

        self.assertEqual(reading["gas_raw"], 700)
        self.assertEqual(reading["sensor_validity_json"], {"temperature": True})
        self.assertEqual(reading["calibration_json"], {"load_cell": "cal-v1"})
        with self.assertRaises(ConflictError):
            self.make_reading(batch, 1, idempotency_key="device-event-1")

    def test_reading_validates_sensor_ranges_and_flags(self):
        batch = self.make_batch()

        with self.assertRaises(ValidationError):
            self.make_reading(batch, 1, temperature_c=90)
        with self.assertRaises(ValidationError):
            self.make_reading(
                batch,
                2,
                temperature_c=None,
                sensor_validity={"temperature": True},
            )
        with self.assertRaises(ValidationError):
            self.make_reading(
                batch,
                3,
                sensor_validity={"temperature": "yes"},
            )

        invalid = self.make_reading(
            batch,
            4,
            temperature_c=None,
            sensor_validity={"temperature": False},
            device_status="online",
        )
        self.assertIsNone(invalid["temperature_c"])
        self.assertEqual(invalid["sensor_validity_json"], {"temperature": False})

    def test_baseline_requires_same_batch_readings_and_marks_readiness(self):
        batch = self.make_batch()
        readings = [self.make_reading(batch, index) for index in range(1, 6)]
        baseline = self.store.establish_baseline(
            batch["batch_id"],
            [reading["reading_id"] for reading in readings],
            ["temperature_c"],
            owner_id="alice",
            algorithm_version="baseline-v1",
        )

        self.assertTrue(baseline["reliable"])
        self.assertEqual(baseline["valid_reading_count"], 5)
        self.assertEqual(baseline["values_json"]["temperature_c"], 22.5)

        mixed_readings = [
            self.make_reading(
                batch,
                index + 10,
                gas_raw=700 if index == 0 else None,
                sensor_validity={
                    "temperature": True,
                    "gas_raw": index == 0,
                },
            )
            for index in range(5)
        ]
        mixed_baseline = self.store.establish_baseline(
            batch["batch_id"],
            [reading["reading_id"] for reading in mixed_readings],
            ["temperature_c", "gas_raw"],
            owner_id="alice",
        )
        self.assertFalse(mixed_baseline["reliable"])
        self.assertEqual(mixed_baseline["valid_reading_count"], 1)

        other_batch = self.make_batch()
        with self.assertRaises(ValidationError):
            self.store.establish_baseline(
                other_batch["batch_id"],
                [readings[0]["reading_id"]],
                ["temperature_c"],
                owner_id="alice",
            )

    def test_observations_keep_source_and_label_provenance(self):
        batch = self.make_batch()
        observation = self.store.add_quality_observation(
            batch["batch_id"],
            observation_source="customer",
            appearance="softening",
            verification_status="unverified",
            owner_id="alice",
        )
        self.assertEqual(observation["verification_status"], "unverified")
        self.assertIsNone(observation["quality_outcome"])

        with self.assertRaises(ValidationError):
            self.store.add_quality_observation(
                batch["batch_id"],
                observation_source="customer",
                quality_outcome="spoiled",
                owner_id="alice",
            )

        labelled = self.store.add_quality_observation(
            batch["batch_id"],
            observation_source="independent_assessor",
            verification_status="verified",
            quality_outcome="confirmed_spoilage",
            label_provenance="assessor review",
            confidence=0.9,
            owner_id="alice",
        )
        self.assertEqual(labelled["label_provenance"], "assessor review")

    def test_references_and_model_metadata_preserve_provenance(self):
        reference = self.store.add_external_reference(
            "Tomato research CSV",
            food_id=self.food["food_id"],
            license="unknown",
            provenance={"source_file": "tomato.csv"},
            schema={"gas_sensor": "MQ array"},
            coverage={"gas": True, "temperature": False},
        )
        self.assertEqual(reference["coverage_json"]["temperature"], False)

        model = self.store.add_model_metadata(
            "rsl-model",
            "1",
            "remaining_shelf_life",
            validation_status="validated",
            supported_food_ids=[self.food["food_id"]],
            artifact_path="models/rsl-v1.joblib",
            feature_order=["temperature_c"],
            evaluation={
                "validation_method": "held_out_batches",
                "metrics": {"mae_days": 1.2},
            },
        )
        self.assertEqual(model["validation_status"], "validated")
        self.assertEqual(model["feature_order_json"], ["temperature_c"])

    def test_shelf_life_requires_validated_food_specific_model(self):
        batch = self.make_batch()
        with self.assertRaises(ValidationError):
            self.store.add_assessment(
                batch["batch_id"],
                "remaining_shelf_life",
                3,
                unit="days",
                owner_id="alice",
            )

        unvalidated_model = self.store.add_model_metadata(
            "unvalidated-rsl",
            "1",
            "remaining_shelf_life",
            supported_food_ids=[self.food["food_id"]],
        )
        with self.assertRaises(ValidationError):
            self.store.add_assessment(
                batch["batch_id"],
                "remaining_shelf_life",
                3,
                unit="days",
                model_id=unvalidated_model["model_id"],
                owner_id="alice",
            )

        with self.assertRaises(ValidationError):
            self.store.add_model_metadata(
                "unsupported-validated-rsl",
                "1",
                "remaining_shelf_life",
                validation_status="validated",
                supported_food_ids=[self.food["food_id"]],
            )

        model = self.store.add_model_metadata(
            "validated-rsl",
            "1",
            "remaining_shelf_life",
            validation_status="validated",
            supported_food_ids=[self.food["food_id"]],
            artifact_path="models/rsl-v1.joblib",
            evaluation={
                "validation_method": "held_out_storage_runs",
                "metrics": {"mae_days": 1.2},
            },
        )
        prediction = self.store.add_assessment(
            batch["batch_id"],
            "remaining_shelf_life",
            3,
            unit="days",
            model_id=model["model_id"],
            owner_id="alice",
        )
        self.assertEqual(prediction["assessment_type"], "remaining_shelf_life")

        risk = self.store.add_assessment(
            batch["batch_id"],
            "freshness_risk",
            60,
            evidence={"basis": "sensor-trends"},
            owner_id="alice",
        )
        self.assertEqual(risk["value"], 60)
        with self.assertRaises(ValidationError):
            self.store.add_assessment(
                batch["batch_id"],
                "freshness_risk",
                150,
                owner_id="alice",
            )

    def test_training_dataset_requires_verified_labels_and_consent(self):
        batch = self.make_batch()
        observation = self.store.add_quality_observation(
            batch["batch_id"],
            observation_source="independent_assessor",
            verification_status="verified",
            quality_outcome="confirmed_spoilage",
            label_provenance="assessor report",
            owner_id="alice",
        )
        self.store.create_training_dataset_version(
            "freshness-v1",
            "freshness_risk",
            source_summary={"customer_observations": 1},
            eligibility_rules={"verified_labels_only": True},
        )

        with self.assertRaises(ValidationError):
            self.store.add_training_dataset_record(
                "freshness-v1",
                batch["batch_id"],
                100,
                "risk_score",
                "verified outcome",
                observation_id=observation["observation_id"],
                owner_id="alice",
            )

        self.store.set_dataset_consent(
            "alice",
            allow_research_use=False,
            allow_training_use=True,
        )
        record = self.store.add_training_dataset_record(
            "freshness-v1",
            batch["batch_id"],
            100,
            "risk_score",
            "verified outcome and explicit training consent",
            observation_id=observation["observation_id"],
            owner_id="alice",
        )
        self.assertEqual(record["batch_id"], batch["batch_id"])
        self.assertEqual(
            len(self.store.list_training_dataset_records(
                "freshness-v1",
                owner_id="alice",
            )),
            1,
        )

    def test_reference_training_records_require_task_coverage_and_sample_id(self):
        batch = self.make_batch()
        self.store.create_training_dataset_version(
            "rsl-v1",
            "remaining_shelf_life",
            source_summary={"external_references": 1},
            eligibility_rules={"compatible_label_coverage": True},
        )
        reference = self.store.add_external_reference(
            "Research reference",
            food_id=self.food["food_id"],
            coverage={"rsl": False},
        )
        with self.assertRaises(ValidationError):
            self.store.add_training_dataset_record(
                "rsl-v1",
                None,
                3,
                "days",
                "unsupported target",
                reference_id=reference["reference_id"],
                source_record_id="row-1",
            )

        compatible_reference = self.store.add_external_reference(
            "Labelled research reference",
            food_id=self.food["food_id"],
            coverage={"rsl": True},
        )
        with self.assertRaises(ValidationError):
            self.store.add_training_dataset_record(
                "rsl-v1",
                None,
                3,
                "days",
                "compatible labelled target",
                reference_id=compatible_reference["reference_id"],
            )
        record = self.store.add_training_dataset_record(
            "rsl-v1",
            None,
            3,
            "days",
            "compatible labelled target",
            reference_id=compatible_reference["reference_id"],
            source_record_id="row-1",
        )
        self.assertIsNone(record["batch_id"])
        self.assertEqual(record["source_record_key"], (
            f"reference:{compatible_reference['reference_id']}:row-1"
        ))

    def test_consent_is_explicit_and_owner_data_can_be_deleted(self):
        batch = self.make_batch()
        self.make_reading(batch, 1)
        consent = self.store.set_dataset_consent(
            "alice",
            allow_research_use=False,
            allow_training_use=True,
        )
        self.assertFalse(consent["allow_research_use"])
        self.assertTrue(consent["allow_training_use"])

        self.store.delete_owner_data("alice")
        self.assertEqual(self.store.list_batches(owner_id="alice"), [])
        with self.assertRaises(NotFoundError):
            self.store.get_batch(batch["batch_id"], owner_id="alice")

    def test_database_persists_across_store_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "freshbox.sqlite3"
            first = FreshBoxStore(database_path)
            food = first.create_food_type("Apple", "fruit")
            first.close()

            second = FreshBoxStore(database_path)
            try:
                self.assertEqual(second.get_food_type(food["food_id"])["display_name"], "Apple")
            finally:
                second.close()


if __name__ == "__main__":
    unittest.main()
