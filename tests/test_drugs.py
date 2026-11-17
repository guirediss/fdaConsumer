import pytest

from app.services.openfda import DrugNotFoundError, OpenFDAIntegrationError


def _label(
    set_id: str,
    generic_name: str,
    brand_name: str | None = None,
) -> dict:
    return {
        "set_id": set_id,
        "generic_name": generic_name,
        "brand_name": brand_name,
        "manufacturer_name": "Example Pharma",
        "route": "ORAL",
        "indications_and_usage": "For use as directed.",
    }


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_deduplicates_and_updates_existing_labels(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: [
            _label("set-1", "sertraline", "Old Brand"),
            _label("set-1", "sertraline", "Updated Brand"),
            _label("set-2", "sertraline", "Another Brand"),
        ],
    )

    first_response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline", "limit": 5},
    )

    assert first_response.status_code == 200
    first_data = first_response.json()
    assert first_data["extracted_count"] == 2
    assert len(first_data["items"]) == 2
    assert first_data["items"][0]["brand_name"] == "Updated Brand"

    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: [
            _label("set-1", "sertraline", "Latest Brand"),
        ],
    )
    second_response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline"},
    )

    assert second_response.status_code == 200
    assert second_response.json()["extracted_count"] == 1

    list_response = client.get("/api/v1/drugs?generic_name=sertraline")
    list_data = list_response.json()
    assert list_data["total"] == 2
    assert next(
        item for item in list_data["items"] if item["set_id"] == "set-1"
    )["brand_name"] == "Latest Brand"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (DrugNotFoundError("No matching drug"), 404),
        (OpenFDAIntegrationError("OpenFDA unavailable"), 502),
    ],
)
def test_extract_maps_openfda_errors(client, monkeypatch, error, status_code):
    def raise_error(generic_name, limit):
        raise error

    monkeypatch.setattr("app.routers.drugs.fetch_drug_labels", raise_error)

    response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline"},
    )

    assert response.status_code == status_code
    assert response.json()["detail"] == str(error)


def test_list_filters_and_paginates_then_gets_drug_by_id(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: [
            _label("set-sertraline-1", "sertraline", "Brand One"),
            _label("set-fluoxetine", "fluoxetine", "Brand Fluoxetine"),
            _label("set-sertraline-2", "sertraline", "Brand Two"),
        ],
    )
    client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline", "limit": 5},
    )

    first_page = client.get(
        "/api/v1/drugs",
        params={"generic_name": "SERTRALINE", "skip": 0, "limit": 1},
    )
    first_data = first_page.json()
    assert first_page.status_code == 200
    assert first_data["total"] == 2
    assert first_data["limit"] == 1
    assert len(first_data["items"]) == 1
    assert first_data["items"][0]["set_id"] == "set-sertraline-2"

    second_page = client.get(
        "/api/v1/drugs",
        params={"generic_name": "sertraline", "skip": 1, "limit": 1},
    )
    second_data = second_page.json()
    assert second_data["total"] == 2
    assert second_data["items"][0]["set_id"] == "set-sertraline-1"

    drug_id = first_data["items"][0]["id"]
    detail = client.get(f"/api/v1/drugs/{drug_id}")
    assert detail.status_code == 200
    assert detail.json()["set_id"] == "set-sertraline-2"

    missing = client.get("/api/v1/drugs/9999")
    assert missing.status_code == 404


def test_extract_rejects_invalid_request_fields(client):
    response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "a", "limit": 26},
    )

    assert response.status_code == 422
