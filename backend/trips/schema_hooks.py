"""drf-spectacular postprocessing hooks (docs/API_CONTRACT.md section 10 component names)."""

from typing import Any

FREE_TEXT_LOCATION = {"type": "string", "minLength": 3, "maxLength": 200}
# COMPONENT_SPLIT_REQUEST suffixes every request-only component with "Request"; the contract names
# these two without it (they are only ever request bodies, so there is no response twin to clash with).
RENAMES = {"PlaceInputRequest": "PlaceInput", "LocationInputRequest": "LocationInput"}
_REF_PREFIX = "#/components/schemas/"


def _rewrite_refs(node: Any) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX):
            node["$ref"] = _REF_PREFIX + RENAMES.get(ref[len(_REF_PREFIX) :], ref[len(_REF_PREFIX) :])
        for value in node.values():
            _rewrite_refs(value)
    elif isinstance(node, list):
        for value in node:
            _rewrite_refs(value)


def finalize_location_components(result: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """LocationInput is `string | PlaceInput` (API_CONTRACT 5.1): add the string branch, fix names."""
    schemas = result.get("components", {}).get("schemas", {})
    location = schemas.get("LocationInputRequest")
    if location is not None and FREE_TEXT_LOCATION not in location["oneOf"]:
        location["oneOf"].insert(0, dict(FREE_TEXT_LOCATION))
    for old, new in RENAMES.items():
        if old in schemas:
            schemas[new] = schemas.pop(old)
    _rewrite_refs(result)
    return result
