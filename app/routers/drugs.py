from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DrugLabel
from app.schemas import (
    DrugExtractRequest,
    DrugExtractResponse,
    DrugLabelResponse,
    DrugListResponse,
)
from app.services.openfda import (
    DrugNotFoundError,
    OpenFDAIntegrationError,
    fetch_drug_labels,
)

router = APIRouter(prefix="/api/v1/drugs", tags=["Drugs"])


def _upsert_labels(db: Session, labels: list[dict]) -> list[DrugLabel]:
    unique_labels = {label["set_id"]: label for label in labels}
    existing_labels = db.scalars(
        select(DrugLabel).where(DrugLabel.set_id.in_(unique_labels))
    ).all()
    existing_by_set_id = {label.set_id: label for label in existing_labels}

    saved_labels: list[DrugLabel] = []
    for set_id, values in unique_labels.items():
        label = existing_by_set_id.get(set_id)
        if label is None:
            label = DrugLabel(**values)
            db.add(label)
        else:
            for field, value in values.items():
                setattr(label, field, value)
        saved_labels.append(label)

    db.commit()
    for label in saved_labels:
        db.refresh(label)

    return saved_labels


@router.post("/extract", status_code=200, response_model=DrugExtractResponse)
def extract_drugs(
    payload: DrugExtractRequest,
    db: Session = Depends(get_db),
) -> DrugExtractResponse:
    try:
        labels = fetch_drug_labels(payload.generic_name, payload.limit)
    except DrugNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OpenFDAIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    saved_labels = _upsert_labels(db, labels)
    return DrugExtractResponse(
        extracted_count=len(saved_labels),
        items=saved_labels,
    )


@router.get("", response_model=DrugListResponse)
def list_drugs(
    generic_name: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DrugListResponse:
    filters = []
    if generic_name is not None:
        filters.append(DrugLabel.generic_name.ilike(f"%{generic_name.strip()}%"))

    total = db.scalar(
        select(func.count()).select_from(DrugLabel).where(*filters)
    )
    items = db.scalars(
        select(DrugLabel)
        .where(*filters)
        .order_by(DrugLabel.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return DrugListResponse(total=total, skip=skip, limit=limit, items=items)


@router.get("/{drug_id}", response_model=DrugLabelResponse)
def get_drug(drug_id: int, db: Session = Depends(get_db)) -> DrugLabel:
    label = db.get(DrugLabel, drug_id)
    if label is None:
        raise HTTPException(status_code=404, detail="Drug label not found")
    return label
