
from fhir.resources.R4B.reference import Reference
import logging
from urllib.parse import unquote
from yarl import URL

from app.models.adjacency.node import NodeReference

logger = logging.getLogger(__name__)

def _node_reference_from_path(parts: list[str]) -> NodeReference:
    if "_history" in parts:
        i = parts.index("_history")
        if i >= 2:
            return NodeReference(resource_type=parts[i - 2], id=parts[i - 1])
        raise ValueError("Invalid reference path")
    if len(parts) >= 2:
        return NodeReference(resource_type=parts[-2], id=parts[-1])
    raise ValueError("Invalid reference path")


def _build_node_reference_from_ref(ref: str, base_url: str) -> NodeReference:
    base_url_norm = base_url.rstrip("/")
    if ref.startswith(base_url_norm):
        ref = ref[len(base_url_norm):].lstrip("/")

    if ref.startswith("https://") or ref.startswith("http://"):  # NOSONAR
        try:
            url = URL(ref)
            parts = [p for p in url.path.split("/") if p]
            return _node_reference_from_path(parts)
        except Exception:
            raise ValueError("Invalid absolute URL found")

    if "?" in ref:
        try:
            url = URL(ref)
            parts = [p for p in url.path.split("/") if p]
            if len(parts) >= 2:
                return _node_reference_from_path(parts)
            if len(parts) == 1:
                resource_type = parts[0]
                query = url.query
                if "_id" in query and query["_id"]:
                    return NodeReference(resource_type=resource_type, id=str(query["_id"]))
                if "_source" in query and query["_source"]:
                    source_ref = unquote(str(query["_source"]))
                    return _build_node_reference_from_ref(source_ref, base_url)
        except Exception:
            logger.error("Failed to parse reference with query: %s", ref)
        raise ValueError("Invalid reference: %s" % ref)

    parts = ref.split("/")
    if len(parts) != 2:
        logger.error("Failed to parse reference: %s", ref)
        raise ValueError("Invalid reference: %s" % ref)

    return NodeReference(resource_type=parts[0], id=parts[1])


def build_node_reference(data: Reference, base_url: str) -> NodeReference:
    """
    Converts a FHIR Reference to a NodeReference, making it relative to the given base URL if necessary.
    """
    ref = data.reference
    if ref is None:
        raise ValueError("Invalid reference (None)")

    return _build_node_reference_from_ref(ref, base_url)