from __future__ import annotations


class ResearchMarkerError(Exception):
    code = "research_marker_error"
    http_status = 400

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class DocumentNotFound(ResearchMarkerError):
    code = "document_not_found"
    http_status = 404


class PageOutOfRange(ResearchMarkerError):
    code = "page_out_of_range"


class PageExtractionFailed(ResearchMarkerError):
    code = "page_extraction_failed"
    http_status = 422


class PageImageUnavailable(ResearchMarkerError):
    code = "page_image_unavailable"
    http_status = 422


class OCRFailed(ResearchMarkerError):
    code = "ocr_failed"
    http_status = 422


class ContextLimitExceeded(ResearchMarkerError):
    code = "context_limit_exceeded"


class ProviderNotInstalled(ResearchMarkerError):
    code = "provider_not_installed"
    http_status = 503


class ProviderNotAuthenticated(ResearchMarkerError):
    code = "provider_not_authenticated"
    http_status = 401


class ProviderAuthenticationExpired(ResearchMarkerError):
    code = "provider_authentication_expired"
    http_status = 401


class ProviderRateLimited(ResearchMarkerError):
    code = "provider_rate_limited"
    http_status = 429


class ProviderUnavailable(ResearchMarkerError):
    code = "provider_unavailable"
    http_status = 503


class GenerationCancelled(ResearchMarkerError):
    code = "generation_cancelled"


class BridgeDisconnected(ResearchMarkerError):
    code = "bridge_disconnected"
    http_status = 503


class ConnectorUnauthorized(ResearchMarkerError):
    code = "connector_unauthorized"
    http_status = 401


class RelayUnavailable(ResearchMarkerError):
    code = "relay_unavailable"
    http_status = 503


class ToolRequestTimedOut(ResearchMarkerError):
    code = "tool_request_timed_out"
    http_status = 504
