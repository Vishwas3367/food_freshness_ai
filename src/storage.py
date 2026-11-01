"""SQLite persistence for FreshBox customer and reference data."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


DEFAULT_OWNER_ID = "local-user"
DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "freshbox.sqlite3"
)
MIN_BASELINE_READINGS = 5


class StorageError(Exception):
    """Base class for persistence and validation errors."""


class ValidationError(StorageError):
    """Raised when a supplied value violates the data contract."""


class NotFoundError(StorageError):
    """Raised when an owner-scoped or global record does not exist."""


class ConflictError(StorageError):
    """Raised when a record conflicts with data already stored."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: str | datetime | None, field: str) -> str:
    if value is None:
        return _utc_now()

    if not isinstance(value, (str, datetime)):
        raise ValidationError(f"{field} must be an ISO-8601 timestamp.")
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp.") from error

    if parsed.tzinfo is None:
        raise ValidationError(f"{field} must include a timezone.")

    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required.")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    text = value.strip()
    return text or None


def _json_object(value: Mapping[str, Any] | None, field: str) -> str:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a JSON object.")
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field} must contain JSON-compatible values.") from error


def _decode_json_fields(record: dict[str, Any], *fields: str) -> dict[str, Any]:
    for field in fields:
        if record.get(field) is not None:
            record[field] = json.loads(record[field])
    return record


def _finite_number(
    value: Any,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number or null.")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be finite.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be at most {maximum}.")
    return number


class FreshBoxStore:
    """Transactional SQLite store; customer data is always owner-scoped."""

    def __init__(self, path: str | Path = DEFAULT_DATABASE_PATH):
        self.path = str(path)
        self._uri = False
        self._keeper: sqlite3.Connection | None = None

        if self.path == ":memory:":
            self.path = f"file:freshbox-{uuid.uuid4()}?mode=memory&cache=shared"
            self._uri = True
            self._keeper = sqlite3.connect(
                self.path,
                uri=True,
                isolation_level=None,
            )
            self._configure_connection(self._keeper)
        else:
            database_path = Path(self.path).expanduser()
            self.path = str(database_path)
            database_path.resolve().parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self._initialize()

    def close(self) -> None:
        if self._keeper is not None:
            self._keeper.close()
            self._keeper = None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            uri=self._uri,
            isolation_level=None,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        self._configure_connection(connection)
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS food_types (
                    food_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    variety TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS food_profiles (
                    profile_id TEXT PRIMARY KEY,
                    food_id TEXT NOT NULL REFERENCES food_types(food_id),
                    version INTEGER NOT NULL CHECK (version > 0),
                    profile_json TEXT NOT NULL,
                    provenance TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (food_id, version)
                );

                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    food_id TEXT NOT NULL REFERENCES food_types(food_id),
                    profile_id TEXT NOT NULL REFERENCES food_profiles(profile_id),
                    name TEXT,
                    initial_weight_g REAL CHECK (
                        initial_weight_g IS NULL OR initial_weight_g >= 0
                    ),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT NOT NULL CHECK (
                        status IN ('created', 'monitoring', 'completed', 'archived')
                    ),
                    storage_json TEXT NOT NULL,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS sensor_readings (
                    reading_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
                    device_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    temperature_c REAL,
                    humidity_pct REAL,
                    gas_raw REAL,
                    gas_calibrated REAL,
                    gas_calibrated_unit TEXT,
                    weight_g REAL,
                    sensor_validity_json TEXT NOT NULL,
                    device_status TEXT NOT NULL CHECK (
                        device_status IN ('online', 'offline', 'unknown')
                    ),
                    calibration_json TEXT NOT NULL,
                    data_source TEXT NOT NULL CHECK (
                        data_source IN (
                            'physical_hardware',
                            'test_data',
                            'external_import',
                            'manual_import'
                        )
                    ),
                    idempotency_key TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (batch_id, device_id, timestamp),
                    UNIQUE (owner_id, idempotency_key),
                    CHECK (temperature_c IS NULL OR temperature_c BETWEEN -40 AND 85),
                    CHECK (humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100),
                    CHECK (gas_raw IS NULL OR gas_raw BETWEEN 0 AND 4095),
                    CHECK (gas_calibrated IS NULL OR gas_calibrated >= 0),
                    CHECK (weight_g IS NULL OR weight_g >= 0),
                    CHECK (
                        (gas_calibrated IS NULL AND gas_calibrated_unit IS NULL)
                        OR
                        (gas_calibrated IS NOT NULL AND gas_calibrated_unit IS NOT NULL)
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_readings_batch_time
                    ON sensor_readings(batch_id, timestamp);

                CREATE TABLE IF NOT EXISTS batch_baselines (
                    baseline_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
                    profile_id TEXT NOT NULL REFERENCES food_profiles(profile_id),
                    source_reading_ids_json TEXT NOT NULL,
                    valid_reading_count INTEGER NOT NULL CHECK (valid_reading_count > 0),
                    reliable INTEGER NOT NULL CHECK (reliable IN (0, 1)),
                    values_json TEXT NOT NULL,
                    algorithm_version TEXT,
                    established_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feature_records (
                    feature_record_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
                    reading_id TEXT NOT NULL REFERENCES sensor_readings(reading_id)
                        ON DELETE CASCADE,
                    profile_id TEXT NOT NULL REFERENCES food_profiles(profile_id),
                    features_json TEXT NOT NULL,
                    processing_metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quality_observations (
                    observation_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
                    observed_at TEXT NOT NULL,
                    appearance TEXT,
                    texture TEXT,
                    notes TEXT,
                    photo_reference TEXT,
                    observation_source TEXT NOT NULL CHECK (
                        observation_source IN (
                            'customer',
                            'authorized_observer',
                            'independent_assessor'
                        )
                    ),
                    verification_status TEXT NOT NULL CHECK (
                        verification_status IN ('unverified', 'verified')
                    ),
                    confidence REAL CHECK (
                        confidence IS NULL OR confidence BETWEEN 0 AND 1
                    ),
                    quality_outcome TEXT,
                    label_provenance TEXT,
                    created_at TEXT NOT NULL,
                    CHECK (
                        quality_outcome IS NULL
                        OR label_provenance IS NOT NULL
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_observations_batch_time
                    ON quality_observations(batch_id, observed_at);

                CREATE TABLE IF NOT EXISTS external_references (
                    reference_id TEXT PRIMARY KEY,
                    food_id TEXT REFERENCES food_types(food_id),
                    name TEXT NOT NULL,
                    source_uri TEXT,
                    license TEXT,
                    provenance_json TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    coverage_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_metadata (
                    model_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    task TEXT NOT NULL,
                    validation_status TEXT NOT NULL CHECK (
                        validation_status IN ('unvalidated', 'experimental', 'validated')
                    ),
                    supported_food_ids_json TEXT NOT NULL,
                    artifact_path TEXT,
                    feature_order_json TEXT NOT NULL,
                    preprocessing_json TEXT NOT NULL,
                    training_dataset_version TEXT,
                    evaluation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (name, version)
                );

                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
                    assessment_type TEXT NOT NULL CHECK (
                        assessment_type IN ('freshness_risk', 'remaining_shelf_life')
                    ),
                    value REAL NOT NULL,
                    unit TEXT,
                    model_id TEXT REFERENCES model_metadata(model_id),
                    confidence REAL CHECK (
                        confidence IS NULL OR confidence BETWEEN 0 AND 1
                    ),
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_consent (
                    owner_id TEXT PRIMARY KEY,
                    allow_research_use INTEGER NOT NULL CHECK (
                        allow_research_use IN (0, 1)
                    ),
                    allow_training_use INTEGER NOT NULL CHECK (
                        allow_training_use IN (0, 1)
                    ),
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS training_dataset_versions (
                    dataset_version TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    source_summary_json TEXT NOT NULL,
                    eligibility_rules_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS training_dataset_records (
                    dataset_record_id TEXT PRIMARY KEY,
                    dataset_version TEXT NOT NULL REFERENCES training_dataset_versions(
                        dataset_version
                    ) ON DELETE CASCADE,
                    owner_id TEXT,
                    batch_id TEXT REFERENCES batches(batch_id) ON DELETE CASCADE,
                    observation_id TEXT REFERENCES quality_observations(observation_id),
                    reference_id TEXT REFERENCES external_references(reference_id),
                    source_record_key TEXT NOT NULL,
                    target_value REAL NOT NULL,
                    target_unit TEXT NOT NULL,
                    selection_reason TEXT NOT NULL,
                    CHECK (
                        (
                            observation_id IS NOT NULL AND reference_id IS NULL
                            AND owner_id IS NOT NULL AND batch_id IS NOT NULL
                        )
                        OR
                        (
                            observation_id IS NULL AND reference_id IS NOT NULL
                            AND owner_id IS NULL AND batch_id IS NULL
                        )
                    ),
                    UNIQUE (dataset_version, source_record_key, target_unit)
                );
                """
            )

    @staticmethod
    def _fetch_one(
        connection: sqlite3.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        row = connection.execute(query, parameters).fetchone()
        return dict(row) if row is not None else None

    def create_food_type(
        self,
        display_name: str,
        category: str,
        *,
        variety: str | None = None,
        profile: Mapping[str, Any] | None = None,
        profile_provenance: str | None = None,
    ) -> dict[str, Any]:
        display_name = _required_text(display_name, "display_name")
        category = _required_text(category, "category").lower()
        if category not in {"fruit", "vegetable", "other"}:
            raise ValidationError("category must be fruit, vegetable, or other.")
        profile_provenance = _optional_text(
            profile_provenance,
            "profile_provenance",
        )
        now = _utc_now()
        food_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())

        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO food_types (
                    food_id, display_name, category, variety, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    food_id,
                    display_name,
                    category,
                    _optional_text(variety, "variety"),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO food_profiles (
                    profile_id, food_id, version, profile_json, provenance, created_at
                ) VALUES (?, ?, 1, ?, ?, ?)
                """,
                (
                    profile_id,
                    food_id,
                    _json_object(profile, "profile"),
                    profile_provenance,
                    now,
                ),
            )

        return self.get_food_type(food_id)

    def get_food_type(self, food_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            food = self._fetch_one(
                connection,
                """
                SELECT f.food_id, f.display_name, f.category, f.variety,
                       f.created_at, f.updated_at,
                       p.profile_id, p.version AS profile_version,
                       p.profile_json, p.provenance AS profile_provenance,
                       p.created_at AS profile_created_at
                FROM food_types f
                JOIN food_profiles p ON p.food_id = f.food_id
                WHERE f.food_id = ?
                ORDER BY p.version DESC
                LIMIT 1
                """,
                (food_id,),
            )
        if food is None:
            raise NotFoundError(f"Food type not found: {food_id}")
        return _decode_json_fields(food, "profile_json")

    def list_food_types(self, search: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT food_id, display_name, category, variety, created_at, updated_at
            FROM food_types
        """
        parameters: tuple[Any, ...] = ()
        if search and search.strip():
            query += " WHERE display_name LIKE ? COLLATE NOCASE"
            parameters = (f"%{search.strip()}%",)
        query += " ORDER BY display_name COLLATE NOCASE"
        with self._connection() as connection:
            return [
                dict(row)
                for row in connection.execute(query, parameters).fetchall()
            ]

    def update_food_profile(
        self,
        food_id: str,
        profile: Mapping[str, Any],
        *,
        provenance: str | None = None,
    ) -> dict[str, Any]:
        encoded_profile = _json_object(profile, "profile")
        provenance = _optional_text(provenance, "provenance")
        now = _utc_now()
        with self._transaction() as connection:
            food = connection.execute(
                "SELECT food_id FROM food_types WHERE food_id = ?",
                (food_id,),
            ).fetchone()
            if food is None:
                raise NotFoundError(f"Food type not found: {food_id}")
            version = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM food_profiles WHERE food_id = ?",
                (food_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO food_profiles (
                    profile_id, food_id, version, profile_json, provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), food_id, version, encoded_profile, provenance, now),
            )
            connection.execute(
                "UPDATE food_types SET updated_at = ? WHERE food_id = ?",
                (now, food_id),
            )
        return self.get_food_type(food_id)

    def create_batch(
        self,
        food_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        name: str | None = None,
        initial_weight_g: float | None = None,
        storage: Mapping[str, Any] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        owner_id = _required_text(owner_id, "owner_id")
        name = _optional_text(name, "name")
        notes = _optional_text(notes, "notes")
        initial_weight_g = _finite_number(
            initial_weight_g,
            "initial_weight_g",
            minimum=0,
        )
        storage_json = _json_object(storage, "storage")
        batch_id = str(uuid.uuid4())
        now = _utc_now()

        with self._transaction() as connection:
            profile = connection.execute(
                """
                SELECT profile_id FROM food_profiles
                WHERE food_id = ? ORDER BY version DESC LIMIT 1
                """,
                (food_id,),
            ).fetchone()
            if profile is None:
                raise NotFoundError(f"Food type not found: {food_id}")
            connection.execute(
                """
                INSERT INTO batches (
                    batch_id, owner_id, food_id, profile_id, name, initial_weight_g,
                    created_at, status, storage_json, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'created', ?, ?)
                """,
                (
                    batch_id,
                    owner_id,
                    food_id,
                    profile["profile_id"],
                    name,
                    initial_weight_g,
                    now,
                    storage_json,
                    notes,
                ),
            )
        return self.get_batch(batch_id, owner_id=owner_id)

    def get_batch(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            batch = self._fetch_one(
                connection,
                """
                SELECT b.*, f.display_name AS food_name, f.category,
                       p.version AS profile_version
                FROM batches b
                JOIN food_types f ON f.food_id = b.food_id
                JOIN food_profiles p ON p.profile_id = b.profile_id
                WHERE b.batch_id = ? AND b.owner_id = ?
                """,
                (batch_id, owner_id),
            )
        if batch is None:
            raise NotFoundError(f"Batch not found: {batch_id}")
        return _decode_json_fields(batch, "storage_json")

    def list_batches(
        self,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        owner_id = _required_text(owner_id, "owner_id")
        query = """
            SELECT b.batch_id, b.owner_id, b.food_id, b.profile_id, b.name,
                   b.initial_weight_g, b.created_at, b.started_at, b.completed_at,
                   b.status, b.storage_json, b.notes, f.display_name AS food_name
            FROM batches b
            JOIN food_types f ON f.food_id = b.food_id
            WHERE b.owner_id = ?
        """
        parameters: tuple[Any, ...] = (owner_id,)
        if status is not None:
            if status not in {"created", "monitoring", "completed", "archived"}:
                raise ValidationError("Invalid batch status.")
            query += " AND b.status = ?"
            parameters += (status,)
        query += " ORDER BY b.created_at DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            _decode_json_fields(dict(row), "storage_json")
            for row in rows
        ]

    def start_batch(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        started_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _timestamp(started_at, "started_at")
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE batches SET status = 'monitoring', started_at = ?
                WHERE batch_id = ? AND owner_id = ? AND status = 'created'
                """,
                (timestamp, batch_id, owner_id),
            )
            if cursor.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM batches WHERE batch_id = ? AND owner_id = ?",
                    (batch_id, owner_id),
                ).fetchone()
                if exists is None:
                    raise NotFoundError(f"Batch not found: {batch_id}")
                raise ConflictError("Only a newly created batch can start monitoring.")
        return self.get_batch(batch_id, owner_id=owner_id)

    def complete_batch(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE batches SET status = 'completed', completed_at = ?
                WHERE batch_id = ? AND owner_id = ? AND status = 'monitoring'
                """,
                (_utc_now(), batch_id, owner_id),
            )
            if cursor.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM batches WHERE batch_id = ? AND owner_id = ?",
                    (batch_id, owner_id),
                ).fetchone()
                if exists is None:
                    raise NotFoundError(f"Batch not found: {batch_id}")
                raise ConflictError("Only a monitored batch can be completed.")
        return self.get_batch(batch_id, owner_id=owner_id)

    def add_sensor_reading(
        self,
        batch_id: str,
        *,
        timestamp: str | datetime,
        temperature_c: float | None = None,
        humidity_pct: float | None = None,
        gas_raw: float | None = None,
        gas_calibrated: float | None = None,
        gas_calibrated_unit: str | None = None,
        weight_g: float | None = None,
        sensor_validity: Mapping[str, Any] | None = None,
        device_status: str = "unknown",
        device_id: str = "default-device",
        calibration: Mapping[str, Any] | None = None,
        data_source: str = "physical_hardware",
        idempotency_key: str | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        owner_id = _required_text(owner_id, "owner_id")
        device_id = _required_text(device_id, "device_id")
        timestamp = _timestamp(timestamp, "timestamp")
        if not isinstance(sensor_validity, Mapping) and sensor_validity is not None:
            raise ValidationError("sensor_validity must be a JSON object.")
        validity = dict(sensor_validity or {})
        if any(not isinstance(value, bool) for value in validity.values()):
            raise ValidationError("sensor_validity values must be booleans.")
        allowed_validity = {
            "temperature",
            "humidity",
            "gas_raw",
            "gas_calibrated",
            "weight",
        }
        unknown_flags = set(validity) - allowed_validity
        if unknown_flags:
            raise ValidationError(
                "Unsupported sensor_validity flags: "
                + ", ".join(sorted(unknown_flags))
            )

        sensor_values = {
            "temperature": temperature_c,
            "humidity": humidity_pct,
            "gas_raw": gas_raw,
            "gas_calibrated": gas_calibrated,
            "weight": weight_g,
        }
        missing_valid_values = [
            sensor for sensor, is_valid in validity.items()
            if is_valid and sensor_values[sensor] is None
        ]
        if missing_valid_values:
            raise ValidationError(
                "A sensor marked valid must include its measurement: "
                + ", ".join(sorted(missing_valid_values))
            )

        temperature_c = _finite_number(
            temperature_c, "temperature_c", minimum=-40, maximum=85
        )
        humidity_pct = _finite_number(
            humidity_pct, "humidity_pct", minimum=0, maximum=100
        )
        gas_raw = _finite_number(gas_raw, "gas_raw", minimum=0, maximum=4095)
        gas_calibrated = _finite_number(
            gas_calibrated, "gas_calibrated", minimum=0
        )
        weight_g = _finite_number(weight_g, "weight_g", minimum=0)
        gas_calibrated_unit = _optional_text(
            gas_calibrated_unit,
            "gas_calibrated_unit",
        )
        if (gas_calibrated is None) != (gas_calibrated_unit is None):
            raise ValidationError(
                "gas_calibrated and gas_calibrated_unit must be provided together."
            )
        if device_status not in {"online", "offline", "unknown"}:
            raise ValidationError("Invalid device_status.")
        if data_source not in {
            "physical_hardware",
            "test_data",
            "external_import",
            "manual_import",
        }:
            raise ValidationError("Invalid data_source.")
        idempotency_key = _optional_text(idempotency_key, "idempotency_key")
        reading_id = str(uuid.uuid4())
        now = _utc_now()

        with self._transaction() as connection:
            batch = connection.execute(
                """
                SELECT 1 FROM batches
                WHERE batch_id = ? AND owner_id = ?
                """,
                (batch_id, owner_id),
            ).fetchone()
            if batch is None:
                raise NotFoundError(f"Batch not found: {batch_id}")
            try:
                connection.execute(
                    """
                    INSERT INTO sensor_readings (
                        reading_id, owner_id, batch_id, device_id, timestamp,
                        temperature_c, humidity_pct, gas_raw, gas_calibrated,
                        gas_calibrated_unit, weight_g, sensor_validity_json,
                        device_status, calibration_json, data_source,
                        idempotency_key, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reading_id,
                        owner_id,
                        batch_id,
                        device_id,
                        timestamp,
                        temperature_c,
                        humidity_pct,
                        gas_raw,
                        gas_calibrated,
                        gas_calibrated_unit,
                        weight_g,
                        _json_object(validity, "sensor_validity"),
                        device_status,
                        _json_object(calibration, "calibration"),
                        data_source,
                        idempotency_key,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed" in str(error):
                    raise ConflictError(
                        "A reading with this idempotency key or device timestamp "
                        "already exists."
                    ) from error
                raise ValidationError(f"Sensor reading was rejected: {error}") from error

        return self.get_sensor_reading(reading_id, owner_id=owner_id)

    def get_sensor_reading(
        self,
        reading_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            reading = self._fetch_one(
                connection,
                """
                SELECT * FROM sensor_readings
                WHERE reading_id = ? AND owner_id = ?
                """,
                (reading_id, owner_id),
            )
        if reading is None:
            raise NotFoundError(f"Sensor reading not found: {reading_id}")
        return _decode_json_fields(
            reading,
            "sensor_validity_json",
            "calibration_json",
        )

    def list_sensor_readings(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be a positive integer.")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM sensor_readings
                WHERE batch_id = ? AND owner_id = ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (batch_id, owner_id, limit),
            ).fetchall()
        return [
            _decode_json_fields(
                dict(row),
                "sensor_validity_json",
                "calibration_json",
            )
            for row in rows
        ]

    def establish_baseline(
        self,
        batch_id: str,
        source_reading_ids: list[str],
        sensor_fields: list[str],
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        algorithm_version: str | None = None,
        established_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        if not isinstance(source_reading_ids, list) or not source_reading_ids:
            raise ValidationError("source_reading_ids must be a non-empty list.")
        source_reading_ids = [
            _required_text(reading_id, "source_reading_id")
            for reading_id in source_reading_ids
        ]
        if len(set(source_reading_ids)) != len(source_reading_ids):
            raise ValidationError("source_reading_ids cannot contain duplicates.")
        if not isinstance(sensor_fields, list) or not sensor_fields:
            raise ValidationError("sensor_fields must be a non-empty list.")
        sensor_columns = {
            "temperature_c": "temperature",
            "humidity_pct": "humidity",
            "gas_raw": "gas_raw",
            "gas_calibrated": "gas_calibrated",
            "weight_g": "weight",
        }
        if any(not isinstance(field, str) for field in sensor_fields):
            raise ValidationError("sensor_fields must contain field names.")
        if len(set(sensor_fields)) != len(sensor_fields):
            raise ValidationError("sensor_fields cannot contain duplicates.")
        unsupported_fields = set(sensor_fields) - set(sensor_columns)
        if unsupported_fields:
            raise ValidationError(
                "Baseline sensor_fields must use canonical sensor fields: "
                + ", ".join(sorted(unsupported_fields))
            )
        algorithm_version = _optional_text(
            algorithm_version,
            "algorithm_version",
        )
        timestamp = _timestamp(established_at, "established_at")
        baseline_id = str(uuid.uuid4())

        with self._transaction() as connection:
            batch = connection.execute(
                """
                SELECT profile_id FROM batches
                WHERE batch_id = ? AND owner_id = ?
                """,
                (batch_id, owner_id),
            ).fetchone()
            if batch is None:
                raise NotFoundError(f"Batch not found: {batch_id}")
            placeholders = ",".join("?" for _ in source_reading_ids)
            rows = connection.execute(
                f"""
                SELECT reading_id, sensor_validity_json, temperature_c,
                       humidity_pct, gas_raw, gas_calibrated, weight_g
                FROM sensor_readings
                WHERE batch_id = ? AND owner_id = ?
                  AND reading_id IN ({placeholders})
                """,
                (batch_id, owner_id, *source_reading_ids),
            ).fetchall()
            if len(rows) != len(source_reading_ids):
                raise ValidationError(
                    "Every baseline reading must belong to this owner's batch."
                )
            valid_counts = {
                column: sum(
                    json.loads(row["sensor_validity_json"]).get(
                        sensor_columns[column]
                    ) is True
                    and row[column] is not None
                    for row in rows
                )
                for column in sensor_fields
            }
            missing_fields = [
                column for column, count in valid_counts.items() if count == 0
            ]
            if missing_fields:
                raise ValidationError(
                    "Baseline fields require valid source readings: "
                    + ", ".join(sorted(missing_fields))
                )
            valid_count = min(valid_counts.values())
            baseline_values = {
                column: sum(
                    float(row[column])
                    for row in rows
                    if json.loads(row["sensor_validity_json"]).get(
                        sensor_columns[column]
                    ) is True
                    and row[column] is not None
                ) / valid_counts[column]
                for column in sensor_fields
            }
            encoded_values = _json_object(baseline_values, "computed baseline")
            connection.execute(
                """
                INSERT INTO batch_baselines (
                    baseline_id, owner_id, batch_id, profile_id,
                    source_reading_ids_json, valid_reading_count, reliable,
                    values_json, algorithm_version, established_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline_id,
                    owner_id,
                    batch_id,
                    batch["profile_id"],
                    _json_object(
                        {"reading_ids": source_reading_ids},
                        "source_reading_ids",
                    ),
                    valid_count,
                    int(valid_count >= MIN_BASELINE_READINGS),
                    encoded_values,
                    algorithm_version,
                    timestamp,
                ),
            )
        return self.get_baseline(baseline_id, owner_id=owner_id)

    def get_baseline(
        self,
        baseline_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            baseline = self._fetch_one(
                connection,
                """
                SELECT * FROM batch_baselines
                WHERE baseline_id = ? AND owner_id = ?
                """,
                (baseline_id, owner_id),
            )
        if baseline is None:
            raise NotFoundError(f"Baseline not found: {baseline_id}")
        baseline = _decode_json_fields(
            baseline,
            "source_reading_ids_json",
            "values_json",
        )
        baseline["reliable"] = bool(baseline["reliable"])
        return baseline

    def add_feature_record(
        self,
        reading_id: str,
        features: Mapping[str, Any],
        *,
        owner_id: str = DEFAULT_OWNER_ID,
        processing_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        feature_id = str(uuid.uuid4())
        with self._transaction() as connection:
            reading = connection.execute(
                """
                SELECT r.batch_id, b.profile_id
                FROM sensor_readings r JOIN batches b ON b.batch_id = r.batch_id
                WHERE r.reading_id = ? AND r.owner_id = ? AND b.owner_id = ?
                """,
                (reading_id, owner_id, owner_id),
            ).fetchone()
            if reading is None:
                raise NotFoundError(f"Sensor reading not found: {reading_id}")
            connection.execute(
                """
                INSERT INTO feature_records (
                    feature_record_id, owner_id, batch_id, reading_id, profile_id,
                    features_json, processing_metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feature_id,
                    owner_id,
                    reading["batch_id"],
                    reading_id,
                    reading["profile_id"],
                    _json_object(features, "features"),
                    _json_object(processing_metadata, "processing_metadata"),
                    _utc_now(),
                ),
            )
        with self._connection() as connection:
            result = self._fetch_one(
                connection,
                "SELECT * FROM feature_records WHERE feature_record_id = ?",
                (feature_id,),
            )
        if result is None:
            raise StorageError("Saved feature record could not be retrieved.")
        return _decode_json_fields(
            result,
            "features_json",
            "processing_metadata_json",
        )

    def add_quality_observation(
        self,
        batch_id: str,
        *,
        observation_source: str,
        verification_status: str = "unverified",
        observed_at: str | datetime | None = None,
        appearance: str | None = None,
        texture: str | None = None,
        notes: str | None = None,
        photo_reference: str | None = None,
        confidence: float | None = None,
        quality_outcome: str | None = None,
        label_provenance: str | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        if observation_source not in {
            "customer",
            "authorized_observer",
            "independent_assessor",
        }:
            raise ValidationError("Invalid observation_source.")
        if verification_status not in {"unverified", "verified"}:
            raise ValidationError("Invalid verification_status.")
        confidence = _finite_number(confidence, "confidence", minimum=0, maximum=1)
        outcome = _optional_text(quality_outcome, "quality_outcome")
        provenance = _optional_text(label_provenance, "label_provenance")
        if outcome is not None and provenance is None:
            raise ValidationError(
                "label_provenance is required when recording a quality outcome."
            )
        observation_id = str(uuid.uuid4())
        timestamp = _timestamp(observed_at, "observed_at")
        with self._transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM batches WHERE batch_id = ? AND owner_id = ?",
                (batch_id, owner_id),
            ).fetchone()
            if exists is None:
                raise NotFoundError(f"Batch not found: {batch_id}")
            connection.execute(
                """
                INSERT INTO quality_observations (
                    observation_id, owner_id, batch_id, observed_at,
                    appearance, texture, notes, photo_reference,
                    observation_source, verification_status, confidence,
                    quality_outcome, label_provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    owner_id,
                    batch_id,
                    timestamp,
                    _optional_text(appearance, "appearance"),
                    _optional_text(texture, "texture"),
                    _optional_text(notes, "notes"),
                    _optional_text(photo_reference, "photo_reference"),
                    observation_source,
                    verification_status,
                    confidence,
                    outcome,
                    provenance,
                    _utc_now(),
                ),
            )
        return self.get_quality_observation(observation_id, owner_id=owner_id)

    def get_quality_observation(
        self,
        observation_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            observation = self._fetch_one(
                connection,
                """
                SELECT * FROM quality_observations
                WHERE observation_id = ? AND owner_id = ?
                """,
                (observation_id, owner_id),
            )
        if observation is None:
            raise NotFoundError(f"Quality observation not found: {observation_id}")
        return observation

    def list_quality_observations(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM quality_observations
                WHERE batch_id = ? AND owner_id = ?
                ORDER BY observed_at DESC
                """,
                (batch_id, owner_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_baselines(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM batch_baselines
                WHERE batch_id = ? AND owner_id = ?
                ORDER BY established_at DESC
                """,
                (batch_id, owner_id),
            ).fetchall()
        baselines = []
        for row in rows:
            baseline = _decode_json_fields(
                dict(row),
                "source_reading_ids_json",
                "values_json",
            )
            baseline["reliable"] = bool(baseline["reliable"])
            baselines.append(baseline)
        return baselines

    def add_external_reference(
        self,
        name: str,
        *,
        food_id: str | None = None,
        source_uri: str | None = None,
        license: str | None = None,
        provenance: Mapping[str, Any] | None = None,
        schema: Mapping[str, Any] | None = None,
        coverage: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        reference_id = str(uuid.uuid4())
        with self._transaction() as connection:
            if food_id is not None and connection.execute(
                "SELECT 1 FROM food_types WHERE food_id = ?",
                (food_id,),
            ).fetchone() is None:
                raise NotFoundError(f"Food type not found: {food_id}")
            connection.execute(
                """
                INSERT INTO external_references (
                    reference_id, food_id, name, source_uri, license,
                    provenance_json, schema_json, coverage_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reference_id,
                    food_id,
                    _required_text(name, "name"),
                    _optional_text(source_uri, "source_uri"),
                    _optional_text(license, "license"),
                    _json_object(provenance, "provenance"),
                    _json_object(schema, "schema"),
                    _json_object(coverage, "coverage"),
                    _utc_now(),
                ),
            )
        with self._connection() as connection:
            result = self._fetch_one(
                connection,
                "SELECT * FROM external_references WHERE reference_id = ?",
                (reference_id,),
            )
        if result is None:
            raise StorageError("Saved external reference could not be retrieved.")
        return _decode_json_fields(
            result,
            "provenance_json",
            "schema_json",
            "coverage_json",
        )

    def list_external_references(
        self,
        food_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM external_references"
        parameters: tuple[Any, ...] = ()
        if food_id is not None:
            query += " WHERE food_id = ?"
            parameters = (food_id,)
        query += " ORDER BY created_at DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            _decode_json_fields(
                dict(row),
                "provenance_json",
                "schema_json",
                "coverage_json",
            )
            for row in rows
        ]

    def add_model_metadata(
        self,
        name: str,
        version: str,
        task: str,
        *,
        validation_status: str = "unvalidated",
        supported_food_ids: list[str] | None = None,
        artifact_path: str | None = None,
        feature_order: list[str] | None = None,
        preprocessing: Mapping[str, Any] | None = None,
        training_dataset_version: str | None = None,
        evaluation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if validation_status not in {"unvalidated", "experimental", "validated"}:
            raise ValidationError("Invalid validation_status.")
        supported_food_ids = supported_food_ids or []
        if not isinstance(supported_food_ids, list):
            raise ValidationError("supported_food_ids must be a list.")
        if not isinstance(feature_order or [], list):
            raise ValidationError("feature_order must be a list.")
        name = _required_text(name, "name")
        version = _required_text(version, "version")
        task = _required_text(task, "task")
        artifact_path = _optional_text(artifact_path, "artifact_path")
        supported_food_ids = list(dict.fromkeys(supported_food_ids))
        feature_order = feature_order or []
        evaluation_data = dict(evaluation or {})
        if validation_status == "validated" and (
            not artifact_path
            or not supported_food_ids
            or evaluation_data.get("validation_method")
            not in {"held_out_batches", "held_out_storage_runs"}
            or not isinstance(evaluation_data.get("metrics"), Mapping)
            or not evaluation_data["metrics"]
        ):
            raise ValidationError(
                "A validated model requires an artifact, supported foods, "
                "held-out batch/storage-run validation, and recorded metrics."
            )
        model_id = str(uuid.uuid4())
        with self._transaction() as connection:
            for food_id in supported_food_ids:
                if connection.execute(
                    "SELECT 1 FROM food_types WHERE food_id = ?",
                    (food_id,),
                ).fetchone() is None:
                    raise NotFoundError(f"Food type not found: {food_id}")
            try:
                connection.execute(
                    """
                    INSERT INTO model_metadata (
                        model_id, name, version, task, validation_status,
                        supported_food_ids_json, artifact_path, feature_order_json,
                        preprocessing_json, training_dataset_version,
                        evaluation_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        name,
                        version,
                        task,
                        validation_status,
                        json.dumps(supported_food_ids),
                        artifact_path,
                        json.dumps(feature_order),
                        _json_object(preprocessing, "preprocessing"),
                        _optional_text(
                            training_dataset_version,
                            "training_dataset_version",
                        ),
                        _json_object(evaluation_data, "evaluation"),
                        _utc_now(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed" in str(error):
                    raise ConflictError(
                        f"Model {name} version {version} already exists."
                    ) from error
                raise
        return self.get_model_metadata(model_id)

    def create_training_dataset_version(
        self,
        dataset_version: str,
        task: str,
        *,
        source_summary: Mapping[str, Any],
        eligibility_rules: Mapping[str, Any],
    ) -> dict[str, Any]:
        dataset_version = _required_text(dataset_version, "dataset_version")
        task = _required_text(task, "task")
        with self._transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO training_dataset_versions (
                        dataset_version, task, source_summary_json,
                        eligibility_rules_json, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_version,
                        task,
                        _json_object(source_summary, "source_summary"),
                        _json_object(eligibility_rules, "eligibility_rules"),
                        _utc_now(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed" in str(error):
                    raise ConflictError(
                        f"Training dataset version already exists: {dataset_version}"
                    ) from error
                raise
            result = self._fetch_one(
                connection,
                """
                SELECT * FROM training_dataset_versions
                WHERE dataset_version = ?
                """,
                (dataset_version,),
            )
        if result is None:
            raise StorageError("Saved training dataset version could not be retrieved.")
        return _decode_json_fields(
            result,
            "source_summary_json",
            "eligibility_rules_json",
        )

    def add_training_dataset_record(
        self,
        dataset_version: str,
        batch_id: str | None,
        target_value: float,
        target_unit: str,
        selection_reason: str,
        *,
        source_record_id: str | None = None,
        observation_id: str | None = None,
        reference_id: str | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        target_value = _finite_number(target_value, "target_value")
        if target_value is None:
            raise ValidationError("target_value is required.")
        target_unit = _required_text(target_unit, "target_unit")
        selection_reason = _required_text(selection_reason, "selection_reason")
        if (observation_id is None) == (reference_id is None):
            raise ValidationError(
                "Provide exactly one verified observation or compatible reference."
            )
        if reference_id is not None and batch_id is not None:
            raise ValidationError(
                "External reference samples must not be assigned to a customer batch."
            )
        if observation_id is not None and batch_id is None:
            raise ValidationError(
                "Customer observation training records require a batch."
            )
        if reference_id is not None:
            source_record_id = _required_text(
                source_record_id,
                "source_record_id",
            )
        record_id = str(uuid.uuid4())
        with self._transaction() as connection:
            dataset = connection.execute(
                """
                SELECT task FROM training_dataset_versions
                WHERE dataset_version = ?
                """,
                (dataset_version,),
            ).fetchone()
            if dataset is None:
                raise NotFoundError(
                    f"Training dataset version not found: {dataset_version}"
                )
            if observation_id is not None:
                batch = connection.execute(
                    """
                    SELECT food_id FROM batches
                    WHERE batch_id = ? AND owner_id = ?
                    """,
                    (batch_id, owner_id),
                ).fetchone()
                if batch is None:
                    raise NotFoundError(f"Batch not found: {batch_id}")
                observation = connection.execute(
                    """
                    SELECT batch_id, verification_status, quality_outcome,
                           label_provenance
                    FROM quality_observations
                    WHERE observation_id = ? AND owner_id = ?
                    """,
                    (observation_id, owner_id),
                ).fetchone()
                if (
                    observation is None
                    or observation["batch_id"] != batch_id
                    or observation["verification_status"] != "verified"
                    or observation["quality_outcome"] is None
                    or observation["label_provenance"] is None
                ):
                    raise ValidationError(
                        "Customer training records require a verified, labelled "
                        "observation from the same batch."
                    )
                consent = connection.execute(
                    """
                    SELECT allow_training_use FROM dataset_consent
                    WHERE owner_id = ?
                    """,
                    (owner_id,),
                ).fetchone()
                if consent is None or not consent["allow_training_use"]:
                    raise ValidationError(
                        "Training use requires the owner's explicit consent."
                    )
                source_key = f"observation:{observation_id}"
                record_owner_id = owner_id
                record_batch_id = batch_id
            else:
                reference = connection.execute(
                    """
                    SELECT coverage_json FROM external_references
                    WHERE reference_id = ?
                    """,
                    (reference_id,),
                ).fetchone()
                if reference is None:
                    raise NotFoundError(f"External reference not found: {reference_id}")
                coverage = json.loads(reference["coverage_json"])
                coverage_key = {
                    "remaining_shelf_life": "rsl",
                    "freshness_risk": "freshness_labels",
                }.get(dataset["task"], dataset["task"])
                if coverage.get(coverage_key) is not True:
                    raise ValidationError(
                        "The reference does not declare compatible labelled coverage "
                        f"for task '{dataset['task']}'."
                    )
                source_key = f"reference:{reference_id}:{source_record_id}"
                record_owner_id = None
                record_batch_id = None

            if dataset["task"] == "remaining_shelf_life" and target_value < 0:
                raise ValidationError("Remaining shelf-life targets cannot be negative.")
            if dataset["task"] == "freshness_risk" and not 0 <= target_value <= 100:
                raise ValidationError(
                    "Freshness-risk targets must be between 0 and 100."
                )

            try:
                connection.execute(
                    """
                    INSERT INTO training_dataset_records (
                        dataset_record_id, dataset_version, owner_id, batch_id,
                        observation_id, reference_id, source_record_key,
                        target_value, target_unit, selection_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        dataset_version,
                        record_owner_id,
                        record_batch_id,
                        observation_id,
                        reference_id,
                        source_key,
                        target_value,
                        target_unit,
                        selection_reason,
                    ),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed" in str(error):
                    raise ConflictError(
                        "This source record is already in the training dataset."
                    ) from error
                raise
            result = self._fetch_one(
                connection,
                """
                SELECT * FROM training_dataset_records
                WHERE dataset_record_id = ?
                """,
                (record_id,),
            )
        if result is None:
            raise StorageError("Saved training record could not be retrieved.")
        return result

    def list_training_dataset_records(
        self,
        dataset_version: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM training_dataset_records
                WHERE dataset_version = ? AND (owner_id = ? OR owner_id IS NULL)
                ORDER BY batch_id, dataset_record_id
                """,
                (dataset_version, owner_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_model_metadata(self, model_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            model = self._fetch_one(
                connection,
                "SELECT * FROM model_metadata WHERE model_id = ?",
                (model_id,),
            )
        if model is None:
            raise NotFoundError(f"Model metadata not found: {model_id}")
        return _decode_json_fields(
            model,
            "supported_food_ids_json",
            "feature_order_json",
            "preprocessing_json",
            "evaluation_json",
        )

    def list_model_metadata(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT model_id FROM model_metadata ORDER BY created_at DESC"
            ).fetchall()
        return [
            self.get_model_metadata(row["model_id"])
            for row in rows
        ]

    def list_assessments(
        self,
        batch_id: str,
        *,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM assessments
                WHERE batch_id = ? AND owner_id = ?
                ORDER BY created_at DESC
                """,
                (batch_id, owner_id),
            ).fetchall()
        return [
            _decode_json_fields(dict(row), "evidence_json")
            for row in rows
        ]

    def add_assessment(
        self,
        batch_id: str,
        assessment_type: str,
        value: float,
        *,
        unit: str | None = None,
        model_id: str | None = None,
        confidence: float | None = None,
        evidence: Mapping[str, Any] | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> dict[str, Any]:
        if assessment_type not in {"freshness_risk", "remaining_shelf_life"}:
            raise ValidationError("Invalid assessment_type.")
        value = _finite_number(value, "value")
        if value is None:
            raise ValidationError("value is required.")
        if assessment_type == "freshness_risk" and not 0 <= value <= 100:
            raise ValidationError("freshness_risk must be between 0 and 100.")
        confidence = _finite_number(confidence, "confidence", minimum=0, maximum=1)
        assessment_id = str(uuid.uuid4())
        with self._transaction() as connection:
            batch = connection.execute(
                """
                SELECT food_id FROM batches
                WHERE batch_id = ? AND owner_id = ?
                """,
                (batch_id, owner_id),
            ).fetchone()
            if batch is None:
                raise NotFoundError(f"Batch not found: {batch_id}")
            if assessment_type == "remaining_shelf_life":
                model = None
                if model_id is not None:
                    model = connection.execute(
                        """
                        SELECT validation_status, task, supported_food_ids_json
                        FROM model_metadata WHERE model_id = ?
                        """,
                        (model_id,),
                    ).fetchone()
                if (
                    model is None
                    or model["validation_status"] != "validated"
                    or model["task"] != "remaining_shelf_life"
                    or batch["food_id"]
                    not in json.loads(model["supported_food_ids_json"])
                ):
                    raise ValidationError(
                        "Remaining-shelf-life assessments require a validated "
                        "model that supports this food type."
                    )
            connection.execute(
                """
                INSERT INTO assessments (
                    assessment_id, owner_id, batch_id, assessment_type, value,
                    unit, model_id, confidence, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    owner_id,
                    batch_id,
                    assessment_type,
                    value,
                    _optional_text(unit, "unit"),
                    model_id,
                    confidence,
                    _json_object(evidence, "evidence"),
                    _utc_now(),
                ),
            )
        with self._connection() as connection:
            result = self._fetch_one(
                connection,
                "SELECT * FROM assessments WHERE assessment_id = ?",
                (assessment_id,),
            )
        if result is None:
            raise StorageError("Saved assessment could not be retrieved.")
        return _decode_json_fields(result, "evidence_json")

    def set_dataset_consent(
        self,
        owner_id: str,
        *,
        allow_research_use: bool,
        allow_training_use: bool,
    ) -> dict[str, Any]:
        owner_id = _required_text(owner_id, "owner_id")
        if not isinstance(allow_research_use, bool) or not isinstance(
            allow_training_use, bool
        ):
            raise ValidationError("Consent values must be booleans.")
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO dataset_consent (
                    owner_id, allow_research_use, allow_training_use, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(owner_id) DO UPDATE SET
                    allow_research_use = excluded.allow_research_use,
                    allow_training_use = excluded.allow_training_use,
                    updated_at = excluded.updated_at
                """,
                (
                    owner_id,
                    int(allow_research_use),
                    int(allow_training_use),
                    _utc_now(),
                ),
            )
            result = self._fetch_one(
                connection,
                "SELECT * FROM dataset_consent WHERE owner_id = ?",
                (owner_id,),
            )
        if result is None:
            raise StorageError("Saved consent could not be retrieved.")
        result["allow_research_use"] = bool(result["allow_research_use"])
        result["allow_training_use"] = bool(result["allow_training_use"])
        return result

    def delete_owner_data(self, owner_id: str) -> None:
        """Delete a user's customer records; global profiles/references remain."""
        owner_id = _required_text(owner_id, "owner_id")
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM batches WHERE owner_id = ?",
                (owner_id,),
            )
            connection.execute(
                "DELETE FROM dataset_consent WHERE owner_id = ?",
                (owner_id,),
            )
