"""OpenAPI authentication metadata tests."""

from src.api.main import app


def test_protected_instrument_operation_exposes_azure_oauth_scheme():
    schema = app.openapi()

    security_schemes = schema["components"]["securitySchemes"]
    azure_scheme = security_schemes["AzureAD_PKCE_single_tenant"]
    operation = schema["paths"]["/api/instruments/check/{ticker}"]["get"]

    assert azure_scheme["type"] == "oauth2"
    assert "authorizationCode" in azure_scheme["flows"]
    assert operation["security"] == [{"AzureAD_PKCE_single_tenant": []}]
