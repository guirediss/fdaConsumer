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


def test_extract_drugs_creates_and_upserts_records(client, monkeypatch):
    labels = [
        _label("set-1", "SERTRALINE", "Brand One"),
        _label("set-2", "SERTRALINE", "Brand Two"),
    ]
    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: labels,
    )
    payload = {"generic_name": "sertraline", "limit": 2}

    first_response = client.post("/api/v1/drugs/extract", json=payload)

    assert first_response.status_code == 200
    assert first_response.json()["extracted_count"] == 2
    assert len(first_response.json()["items"]) == 2

    labels[0] = _label("set-1", "SERTRALINE", "Updated Brand")
    second_response = client.post("/api/v1/drugs/extract", json=payload)

    assert second_response.status_code == 200
    assert second_response.json()["extracted_count"] == 2

    list_response = client.get("/api/v1/drugs")
    list_data = list_response.json()
    assert list_data["total"] == 2
    assert next(item for item in list_data["items"] if item["set_id"] == "set-1")[
        "brand_name"
    ] == "Updated Brand"


def test_extract_drugs_returns_404_when_not_found(client, monkeypatch):
    def raise_not_found(generic_name, limit):
        raise DrugNotFoundError("No OpenFDA labels found")

    monkeypatch.setattr("app.routers.drugs.fetch_drug_labels", raise_not_found)

    response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No OpenFDA labels found"


def test_extract_drugs_returns_502_on_external_failure(client, monkeypatch):
    def raise_integration_error(generic_name, limit):
        raise OpenFDAIntegrationError("OpenFDA unavailable")

    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        raise_integration_error,
    )

    response = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenFDA unavailable"


def test_list_drugs_supports_filter_and_pagination(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: [
            _label("set-sertraline-1", "SERTRALINE", "Brand One"),
            _label("set-aspirin", "ASPIRIN", "Brand Aspirin"),
            _label("set-sertraline-2", "SERTRALINE", "Brand Two"),
        ],
    )
    client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline", "limit": 3},
    )

    response = client.get(
        "/api/v1/drugs",
        params={"generic_name": "sertraline", "skip": 0, "limit": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["skip"] == 0
    assert data["limit"] == 1


def test_get_drug_by_id_and_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.drugs.fetch_drug_labels",
        lambda generic_name, limit: [_label("set-1", "SERTRALINE", "Brand One")],
    )
    extraction = client.post(
        "/api/v1/drugs/extract",
        json={"generic_name": "sertraline"},
    )
    drug_id = extraction.json()["items"][0]["id"]

    found = client.get(f"/api/v1/drugs/{drug_id}")
    missing = client.get("/api/v1/drugs/9999")

    assert found.status_code == 200
    assert found.json()["set_id"] == "set-1"
    assert missing.status_code == 404


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"generic_name": "s"}, 422),
        ({"generic_name": "sertraline", "limit": 0}, 422),
        ({"generic_name": "sertraline", "limit": 26}, 422),
    ],
)
def test_extract_rejects_invalid_payload(client, payload, expected_status):
    response = client.post("/api/v1/drugs/extract", json=payload)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"skip": -1}, 422),
        ({"limit": 0}, 422),
        ({"limit": 101}, 422),
    ],
)
def test_list_rejects_invalid_pagination(client, params, expected_status):
    response = client.get("/api/v1/drugs", params=params)

    assert response.status_code == expected_status


def test_list_returns_empty_result_when_filter_has_no_matches(client):
    response = client.get("/api/v1/drugs", params={"generic_name": "unknown"})

    assert response.status_code == 200
    assert response.json() == {"total": 0, "skip": 0, "limit": 20, "items": []}


def test_get_drug_rejects_non_integer_id(client):
    response = client.get("/api/v1/drugs/not-an-id")

    assert response.status_code == 422
