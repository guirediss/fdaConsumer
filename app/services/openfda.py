from typing import Any

import httpx

from app.config import settings


class DrugNotFoundError(Exception):
    pass


class OpenFDAIntegrationError(Exception):
    pass


def _first_value(values: Any) -> str | None:
    if isinstance(values, (list, tuple)):
        values = values[0] if values else None
    if not isinstance(values, str):
        return None

    value = values.strip()
    return value or None


def _build_params(generic_name: str, limit: int) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "search": f'openfda.generic_name:"{generic_name}"',
        "limit": limit,
    }

    api_key = settings.OPENFDA_API_KEY
    if (
        api_key
        and api_key.strip()
        and api_key.strip() != "your_openfda_api_key_here"
    ):
        params["api_key"] = api_key.strip()

    return params


def _fetch_results(search_term: str, params: dict[str, str | int]) -> list[Any]:
    try:
        response = httpx.get(settings.OPENFDA_BASE_URL, params=params, timeout=10.0)
    except httpx.RequestError as exc:
        raise OpenFDAIntegrationError("Could not reach the OpenFDA API") from exc

    if response.status_code == 404:
        raise DrugNotFoundError(f"No OpenFDA labels found for {search_term!r}")

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenFDAIntegrationError(
            f"OpenFDA returned HTTP {exc.response.status_code}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenFDAIntegrationError("OpenFDA returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise OpenFDAIntegrationError("OpenFDA returned an invalid response")

    results = payload.get("results", [])
    if not isinstance(results, list):
        raise OpenFDAIntegrationError("OpenFDA returned an invalid results list")
    if not results:
        raise DrugNotFoundError(f"No OpenFDA labels found for {search_term!r}")

    return results


def _normalize_label(item: Any, search_term: str) -> dict | None:
    if not isinstance(item, dict):
        return None

    set_id = item.get("set_id") or item.get("id")
    if not set_id:
        return None

    openfda = item.get("openfda")
    if not isinstance(openfda, dict):
        openfda = {}

    indications = item.get("indications_and_usage")
    if isinstance(indications, list):
        indications_value = "\n".join(
            value for value in indications if isinstance(value, str)
        ) or None
    elif isinstance(indications, str):
        indications_value = indications or None
    else:
        indications_value = None

    return {
        "set_id": str(set_id),
        "generic_name": _first_value(openfda.get("generic_name"))
        or search_term.upper(),
        "brand_name": _first_value(openfda.get("brand_name")),
        "manufacturer_name": _first_value(openfda.get("manufacturer_name")),
        "route": _first_value(openfda.get("route")),
        "indications_and_usage": indications_value,
    }


def fetch_drug_labels(generic_name: str, limit: int = 5) -> list[dict]:
    search_term = generic_name.strip()
    results = _fetch_results(search_term, _build_params(search_term, limit))
    normalized_items = [
        normalized
        for item in results
        if (normalized := _normalize_label(item, search_term)) is not None
    ]
    if not normalized_items:
        raise DrugNotFoundError(f"No OpenFDA labels found for {search_term!r}")

    return normalized_items
