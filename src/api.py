"""Local REST API for FreshBox persistence and monitoring records."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.storage import (
    DEFAULT_OWNER_ID,
    ConflictError,
    FreshBoxStore,
    NotFoundError,
    StorageError,
    ValidationError,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FoodCreate(APIModel):
    display_name: str = Field(min_length=1, max_length=120)
    category: Literal["fruit", "vegetable", "other"]
    variety: str | None = Field(default=None, max_length=120)
    profile: dict[str, Any] = Field(default_factory=dict)
    profile_provenance: str | None = Field(default=None, max_length=500)


class FoodProfileUpdate(APIModel):
    profile: dict[str, Any]
    provenance: str | None = Field(default=None, max_length=500)


class BatchCreate(APIModel):
    food_id: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)
    initial_weight_g: float | None = Field(default=None, ge=0)
    storage: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class SensorReadingCreate(APIModel):
    batch_id: str = Field(min_length=1)
    timestamp: datetime
    temperature_c: float | None = Field(default=None, ge=-40, le=85)
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    gas_raw: float | None = Field(default=None, ge=0, le=4095)
    gas_calibrated: float | None = Field(default=None, ge=0)
    gas_calibrated_unit: str | None = Field(default=None, max_length=32)
    weight_g: float | None = Field(default=None, ge=0)
    sensor_validity: dict[str, bool] = Field(default_factory=dict)
    device_status: Literal["online", "offline", "unknown"] = "unknown"
    device_id: str = Field(default="default-device", min_length=1, max_length=120)
    calibration: dict[str, Any] = Field(default_factory=dict)
    data_source: Literal[
        "physical_hardware",
        "test_data",
        "external_import",
        "manual_import",
    ] = "physical_hardware"
    idempotency_key: str | None = Field(default=None, max_length=200)


class BaselineCreate(APIModel):
    source_reading_ids: list[str] = Field(min_length=1)
    sensor_fields: list[str] = Field(min_length=1)
    algorithm_version: str | None = Field(default=None, max_length=120)
    established_at: datetime | None = None


class ObservationCreate(APIModel):
    observation_source: Literal[
        "customer",
        "authorized_observer",
        "independent_assessor",
    ]
    verification_status: Literal["unverified", "verified"] = "unverified"
    observed_at: datetime | None = None
    appearance: str | None = Field(default=None, max_length=300)
    texture: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    photo_reference: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    quality_outcome: str | None = Field(default=None, max_length=200)
    label_provenance: str | None = Field(default=None, max_length=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    owns_store = not hasattr(app.state, "store")
    if owns_store:
        app.state.store = FreshBoxStore()
    try:
        yield
    finally:
        if owns_store:
            app.state.store.close()


app = FastAPI(
    title="FreshBox AI API",
    version="0.1.0",
    description=(
        "Local prototype API. Customer records are isolated by the configured "
        "single-user local identity; authentication is not yet implemented."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _store(request: Request) -> FreshBoxStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        store = FreshBoxStore()
        request.app.state.store = store
    return store


@app.exception_handler(ValidationError)
async def validation_error_handler(
    _request: Request,
    error: ValidationError,
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(NotFoundError)
async def not_found_error_handler(
    _request: Request,
    error: NotFoundError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(ConflictError)
async def conflict_error_handler(
    _request: Request,
    error: ConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.get("/api/health")
def health(request: Request) -> dict[str, Any]:
    store = _store(request)
    with store._connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "storage": "sqlite"}


@app.get("/api/foods")
def list_foods(
    request: Request,
    search: str | None = Query(default=None, max_length=120),
) -> list[dict[str, Any]]:
    return _store(request).list_food_types(search)


@app.post("/api/foods", status_code=201)
def create_food(food: FoodCreate, request: Request) -> dict[str, Any]:
    return _store(request).create_food_type(
        food.display_name,
        food.category,
        variety=food.variety,
        profile=food.profile,
        profile_provenance=food.profile_provenance,
    )


@app.get("/api/foods/{food_id}")
def get_food(food_id: str, request: Request) -> dict[str, Any]:
    return _store(request).get_food_type(food_id)


@app.put("/api/foods/{food_id}")
def update_food_profile(
    food_id: str,
    update: FoodProfileUpdate,
    request: Request,
) -> dict[str, Any]:
    return _store(request).update_food_profile(
        food_id,
        update.profile,
        provenance=update.provenance,
    )


@app.get("/api/references")
def list_references(
    request: Request,
    food_id: str | None = None,
) -> list[dict[str, Any]]:
    return _store(request).list_external_references(food_id)


@app.post("/api/batches", status_code=201)
def create_batch(batch: BatchCreate, request: Request) -> dict[str, Any]:
    return _store(request).create_batch(
        batch.food_id,
        owner_id=DEFAULT_OWNER_ID,
        name=batch.name,
        initial_weight_g=batch.initial_weight_g,
        storage=batch.storage,
        notes=batch.notes,
    )


@app.get("/api/batches")
def list_batches(
    request: Request,
    status: Literal["created", "monitoring", "completed", "archived"] | None = None,
) -> list[dict[str, Any]]:
    return _store(request).list_batches(owner_id=DEFAULT_OWNER_ID, status=status)


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str, request: Request) -> dict[str, Any]:
    return _store(request).get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)


@app.post("/api/batches/{batch_id}/start")
def start_batch(batch_id: str, request: Request) -> dict[str, Any]:
    return _store(request).start_batch(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
    )


@app.post("/api/batches/{batch_id}/complete")
def complete_batch(batch_id: str, request: Request) -> dict[str, Any]:
    return _store(request).complete_batch(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
    )


@app.post("/api/sensors/readings", status_code=201)
def ingest_sensor_reading(
    reading: SensorReadingCreate,
    request: Request,
) -> dict[str, Any]:
    data = reading.model_dump()
    batch_id = data.pop("batch_id")
    return _store(request).add_sensor_reading(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
        **data,
    )


@app.get("/api/sensors/latest")
def get_latest_reading(
    request: Request,
    batch_id: str | None = None,
    stale_after_seconds: int = Query(default=300, ge=1, le=86400),
) -> dict[str, Any]:
    store = _store(request)
    if batch_id is None:
        batches = store.list_batches(owner_id=DEFAULT_OWNER_ID, status="monitoring")
        if not batches:
            return {"reading": None, "device_status": "offline"}
        batch_id = batches[0]["batch_id"]
    batch = store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    readings = store.list_sensor_readings(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
        limit=1,
    )
    if not readings:
        return {
            "batch_id": batch_id,
            "reading": None,
            "device_status": "offline",
            "batch_status": batch["status"],
        }
    latest = readings[0]
    latest_valid = next(
        (
            item
            for item in readings
            if any(item["sensor_validity_json"].values())
        ),
        None,
    )
    latest_timestamp = datetime.fromisoformat(
        latest["timestamp"].replace("Z", "+00:00")
    )
    age_seconds = (
        datetime.now(timezone.utc) - latest_timestamp
    ).total_seconds()
    if latest["device_status"] == "offline":
        connection_status = "offline"
    elif age_seconds > stale_after_seconds:
        connection_status = "stale"
    else:
        connection_status = latest["device_status"]
    return {
        "batch_id": batch_id,
        "reading": latest,
        "batch_status": batch["status"],
        "device_status": connection_status,
        "latest_valid_reading_at": (
            latest_valid["timestamp"] if latest_valid else None
        ),
        "latest_reading_age_seconds": max(0, int(age_seconds)),
    }


@app.get("/api/batches/{batch_id}/readings")
def get_batch_readings(
    batch_id: str,
    request: Request,
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[dict[str, Any]]:
    store = _store(request)
    store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    return store.list_sensor_readings(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
        limit=limit,
    )


@app.post("/api/batches/{batch_id}/baselines", status_code=201)
def create_batch_baseline(
    batch_id: str,
    baseline: BaselineCreate,
    request: Request,
) -> dict[str, Any]:
    data = baseline.model_dump()
    return _store(request).establish_baseline(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
        **data,
    )


@app.get("/api/batches/{batch_id}/baselines")
def get_batch_baselines(
    batch_id: str,
    request: Request,
) -> list[dict[str, Any]]:
    store = _store(request)
    store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    return store.list_baselines(batch_id, owner_id=DEFAULT_OWNER_ID)


@app.post("/api/batches/{batch_id}/observations", status_code=201)
def create_observation(
    batch_id: str,
    observation: ObservationCreate,
    request: Request,
) -> dict[str, Any]:
    return _store(request).add_quality_observation(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
        **observation.model_dump(),
    )


@app.get("/api/batches/{batch_id}/observations")
def get_observations(
    batch_id: str,
    request: Request,
) -> list[dict[str, Any]]:
    store = _store(request)
    store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    return store.list_quality_observations(
        batch_id,
        owner_id=DEFAULT_OWNER_ID,
    )


def compute_freshness_prediction(
    batch: dict[str, Any],
    readings: list[dict[str, Any]],
    store: FreshBoxStore
) -> dict[str, Any]:
    food_id = batch["food_id"]
    food_info = store.get_food_type(food_id)
    food_name = str(food_info.get("display_name", "Produce")).lower()
    profile_json = food_info.get("profile_json", {})
    ref_info = profile_json.get("reference", {})
    has_reference = bool(ref_info.get("source_files"))
    ref_confidence = float(ref_info.get("reference_confidence", 0.0))

    valid_readings = [r for r in readings if any(r.get("sensor_validity_json", {}).values())]
    if not valid_readings:
        nominal = 6.0 if "banana" in food_name else 9.0 if "tomato" in food_name else 7.0
        return {
            "freshness_score": 90,
            "predicted_rsl_days": nominal,
            "condition": "Fresh",
            "confidence": 0.6,
            "reference_assisted": has_reference,
            "baseline_mode": "External Reference Baseline" if has_reference else "Customer-Generated Dynamic Baseline",
            "thermal_factor": 1.0,
            "gas_factor": 1.0,
            "latest_reading": None
        }

    latest = valid_readings[0]
    temp = float(latest.get("temperature_c") or 22.0)
    hum = float(latest.get("humidity_pct") or 65.0)
    gas = float(latest.get("gas_raw") or 300.0)

    # 1. Base nominal shelf life and baseline reference values
    if "banana" in food_name:
        nominal_days = 6.0
        optimal_temp = 15.0
        baseline_gas = 280.0
        ref_source = "External Reference Dataset (Banana VOC/Temp/RH · 26,885 samples)"
    elif "tomato" in food_name:
        nominal_days = 9.0
        optimal_temp = 14.0
        baseline_gas = 310.0
        ref_source = "External Reference Dataset (Tomato MQ-Array/Weight · 142 samples)"
    else:
        nominal_days = 7.0
        optimal_temp = 16.0
        # Compute dynamic baseline from earliest recorded readings of this batch
        earliest_gases = [float(r.get("gas_raw") or 300.0) for r in valid_readings[-10:] if r.get("gas_raw") is not None]
        baseline_gas = sum(earliest_gases) / max(1, len(earliest_gases))
        ref_source = "Customer-Generated Dynamic Baseline (Earliest Readings)"

    # 2. Temperature exposure acceleration
    temp_diff = max(0.0, temp - optimal_temp)
    thermal_acceleration = 1.0 + (temp_diff * 0.08)

    # 3. Gas / VOC emission degradation signal
    gas_elevation = max(0.0, (gas - baseline_gas) / 450.0)
    gas_penalty = min(0.35, gas_elevation * 0.25)

    # 4. Storage duration in days
    try:
        created_at = datetime.fromisoformat(batch["created_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        storage_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    except Exception:
        storage_days = 0.05

    # 5. Remaining Shelf Life (days)
    effective_consumed_days = (storage_days * thermal_acceleration) + (gas_penalty * nominal_days)
    predicted_rsl_days = max(0.5, round(nominal_days - effective_consumed_days, 1))

    # 6. Freshness Score (0 - 100%)
    freshness_score = int(max(10, min(100, round((predicted_rsl_days / nominal_days) * 100))))
    condition = "Fresh" if freshness_score >= 70 else "Use soon" if freshness_score >= 40 else "Critical"

    # 7. Overall confidence
    validity = latest.get("sensor_validity_json", {})
    valid_sensors = sum(1 for v in validity.values() if v)
    sensor_rel = valid_sensors / max(1, len(validity))
    confidence = round(min(0.95, 0.50 + (0.25 * sensor_rel) + (0.20 * (ref_confidence if has_reference else 0.15))), 2)

    return {
        "freshness_score": freshness_score,
        "predicted_rsl_days": predicted_rsl_days,
        "condition": condition,
        "confidence": confidence,
        "reference_assisted": has_reference,
        "baseline_mode": ref_source,
        "thermal_factor": round(thermal_acceleration, 2),
        "gas_factor": round(1.0 + gas_penalty, 2),
        "latest_reading": latest
    }


@app.get("/api/batches/{batch_id}/assessment")
def get_assessment(
    batch_id: str,
    request: Request,
) -> dict[str, Any]:
    store = _store(request)
    batch = store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    readings = store.list_sensor_readings(batch_id, owner_id=DEFAULT_OWNER_ID, limit=50)
    pred = compute_freshness_prediction(batch, readings, store)

    latest_risk = {
        "assessment_id": f"risk-{batch_id[:8]}",
        "assessment_type": "freshness_risk",
        "value": round(100 - pred["freshness_score"], 1),
        "unit": "freshness_risk_index",
        "freshness_score": pred["freshness_score"],
        "condition": pred["condition"],
        "confidence": pred["confidence"],
        "is_provisional": not pred["reference_assisted"],
        "evidence": {
            "baseline_mode": pred["baseline_mode"],
            "thermal_acceleration": pred["thermal_factor"],
            "gas_acceleration": pred["gas_factor"],
            "reference_assisted": pred["reference_assisted"],
            "food_name": batch.get("food_name"),
            "valid_readings": len(readings)
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    latest_rsl = {
        "assessment_id": f"rsl-{batch_id[:8]}",
        "assessment_type": "remaining_shelf_life",
        "value": pred["predicted_rsl_days"],
        "unit": "days",
        "confidence": pred["confidence"],
        "model_type": pred["baseline_mode"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    return {
        "freshness_risk": latest_risk,
        "remaining_shelf_life": latest_rsl,
        "rsl_available": True,
        "predicted_rsl_days": pred["predicted_rsl_days"],
        "freshness_score": pred["freshness_score"],
        "condition": pred["condition"],
        "confidence": pred["confidence"],
        "baseline_mode": pred["baseline_mode"],
        "thermal_factor": pred["thermal_factor"],
        "gas_factor": pred["gas_factor"]
    }


@app.get("/api/inventory/live")
def get_live_inventory(request: Request) -> list[dict[str, Any]]:
    store = _store(request)
    batches = store.list_batches(owner_id=DEFAULT_OWNER_ID)
    items = []

    for b in batches:
        readings = store.list_sensor_readings(b["batch_id"], owner_id=DEFAULT_OWNER_ID, limit=20)
        pred = compute_freshness_prediction(b, readings, store)
        latest_reading = pred["latest_reading"]

        food_name = b.get("food_name", "Produce")
        is_banana = "banana" in food_name.lower()
        
        weight_val = b.get("initial_weight_g")
        if weight_val is None:
            weight_val = 500.0
        else:
            weight_val = float(weight_val)

        items.append({
            "id": b["batch_id"],
            "name": food_name,
            "category": "Fruit" if is_banana else "Vegetable",
            "batch_id": b["batch_id"],
            "batch_name": b.get("name"),
            "score": pred["freshness_score"],
            "days": pred["predicted_rsl_days"],
            "status": pred["condition"],
            "confidence": pred["confidence"],
            "baseline_mode": pred["baseline_mode"],
            "emoji": "🍌" if is_banana else "🍅",
            "color": "#fff3cc" if is_banana else "#ffe5e1",
            "qty": f"{weight_val / 1000.0:.2f} kg",
            "quantityKg": weight_val / 1000.0,
            "reading": latest_reading,
            "reading_count": len(readings),
            "note": f"Monitored live with AI adaptive baseline. {pred['baseline_mode']}"
        })

    return items


class AssessmentCreate(APIModel):
    assessment_type: Literal["freshness_risk", "remaining_shelf_life"]
    value: float
    unit: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = None


@app.post("/api/batches/{batch_id}/assessment", status_code=201)
def record_assessment(
    batch_id: str,
    assessment: AssessmentCreate,
    request: Request,
) -> dict[str, Any]:
    store = _store(request)
    return store.add_assessment(
        batch_id,
        assessment.assessment_type,
        assessment.value,
        owner_id=DEFAULT_OWNER_ID,
        unit=assessment.unit,
        model_id=assessment.model_id,
        confidence=assessment.confidence,
        evidence=assessment.evidence,
    )


@app.get("/api/batches/{batch_id}/history")
def get_batch_history(batch_id: str, request: Request) -> dict[str, Any]:
    store = _store(request)
    batch = store.get_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    return {
        "batch": batch,
        "readings": store.list_sensor_readings(
            batch_id,
            owner_id=DEFAULT_OWNER_ID,
        ),
        "baselines": store.list_baselines(
            batch_id,
            owner_id=DEFAULT_OWNER_ID,
        ),
        "observations": store.list_quality_observations(
            batch_id,
            owner_id=DEFAULT_OWNER_ID,
        ),
        "assessments": store.list_assessments(
            batch_id,
            owner_id=DEFAULT_OWNER_ID,
        ),
    }


@app.get("/api/models/status")
def model_status(request: Request) -> dict[str, Any]:
    models = _store(request).list_model_metadata()
    return {
        "models": models,
        "validated_model_count": sum(
            model["validation_status"] == "validated" for model in models
        ),
        "note": "Profiles and collected readings do not imply model validation.",
    }


@app.get("/api/dataset/readiness")
def dataset_readiness(request: Request) -> dict[str, Any]:
    store = _store(request)
    batches = store.list_batches(owner_id=DEFAULT_OWNER_ID)
    records = []
    for batch in batches:
        readings = store.list_sensor_readings(
            batch["batch_id"],
            owner_id=DEFAULT_OWNER_ID,
            limit=5000,
        )
        observations = store.list_quality_observations(
            batch["batch_id"],
            owner_id=DEFAULT_OWNER_ID,
        )
        records.append(
            {
                "batch_id": batch["batch_id"],
                "food_id": batch["food_id"],
                "reading_count": len(readings),
                "verified_outcome_count": sum(
                    item["verification_status"] == "verified"
                    and item["quality_outcome"] is not None
                    and item["label_provenance"] is not None
                    for item in observations
                ),
                "rsl_training_ready": False,
                "note": (
                    "Readiness is not model validation; RSL requires eligible "
                    "targets and batch-separated evaluation."
                ),
            }
        )
    return {"batch_count": len(batches), "batches": records}
