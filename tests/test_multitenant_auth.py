"""
Tests for multitenant authentication middleware and chat handler.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.middleware.tenant_auth import (
    TenantContext,
    get_tenant_context,
    get_optional_tenant_context,
    verify_freshdesk_api_key,
    extract_tenant_from_domain,
    SUPPORTED_PLATFORMS,
)
from app.models.metadata import MetadataFilter

# Use anyio for async tests
pytestmark = pytest.mark.anyio


def make_mock_request(headers_dict: dict):
    """Helper to create a mock request with proper headers."""
    request = MagicMock()
    mock_headers = MagicMock()
    mock_headers.get = lambda k, d="": headers_dict.get(k, d)
    request.headers = mock_headers
    return request


class TestTenantContext:
    """Tests for TenantContext dataclass."""

    def test_tenant_context_creation(self):
        """Test creating a tenant context."""
        context = TenantContext(
            tenant_id="wedosoft",
            platform="freshdesk",
            domain="wedosoft.freshdesk.com",
            verified=True,
        )
        
        assert context.tenant_id == "wedosoft"
        assert context.platform == "freshdesk"
        assert context.verified is True

    def test_mandatory_filters(self):
        """Test that mandatory filters are generated correctly."""
        context = TenantContext(
            tenant_id="acme",
            platform="zendesk",
            verified=True,
            mandatory_filters=[
                MetadataFilter(key="tenant_id", value="acme", operator="EQUALS"),
                MetadataFilter(key="platform", value="zendesk", operator="EQUALS"),
            ],
        )
        
        filters = context.get_mandatory_filters()
        
        assert len(filters) == 2
        assert filters[0].key == "tenant_id"
        assert filters[0].value == "acme"
        assert filters[1].key == "platform"
        assert filters[1].value == "zendesk"

    def test_mandatory_filters_copy(self):
        """Test that get_mandatory_filters returns a copy."""
        original_filters = [
            MetadataFilter(key="tenant_id", value="test", operator="EQUALS"),
        ]
        context = TenantContext(
            tenant_id="test",
            platform="freshdesk",
            mandatory_filters=original_filters,
        )
        
        filters = context.get_mandatory_filters()
        filters.append(MetadataFilter(key="extra", value="value", operator="EQUALS"))
        
        # Original should be unchanged
        assert len(context.mandatory_filters) == 1


class TestExtractTenantFromDomain:
    """Tests for domain parsing."""

    def test_freshdesk_domain(self):
        """Test extracting tenant from Freshdesk domain."""
        assert extract_tenant_from_domain("wedosoft.freshdesk.com", "freshdesk") == "wedosoft"

    def test_zendesk_domain(self):
        """Test extracting tenant from Zendesk domain."""
        assert extract_tenant_from_domain("acme.zendesk.com", "zendesk") == "acme"

    def test_domain_with_protocol(self):
        """Test extracting tenant from domain with protocol."""
        assert extract_tenant_from_domain("https://company.freshdesk.com", "freshdesk") == "company"

    def test_simple_domain(self):
        """Test with simple domain."""
        assert extract_tenant_from_domain("mycompany", "web") == "mycompany"

    def test_empty_domain(self):
        """Test with empty domain."""
        assert extract_tenant_from_domain("", "freshdesk") == ""


class TestVerifyFreshdeskApiKey:
    """Tests for Freshdesk API key verification."""

    async def test_verify_with_empty_credentials(self):
        """Test that empty credentials return False."""
        assert await verify_freshdesk_api_key("", "api_key") is False
        assert await verify_freshdesk_api_key("domain", "") is False
        assert await verify_freshdesk_api_key("", "") is False

    async def test_verify_success(self):
        """Test successful API key verification."""
        with patch("app.middleware.tenant_auth.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await verify_freshdesk_api_key("wedosoft", "valid_key")
            
            assert result is True

    async def test_verify_failure(self):
        """Test failed API key verification."""
        with patch("app.middleware.tenant_auth.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance
            
            result = await verify_freshdesk_api_key("wedosoft", "invalid_key")
            
            assert result is False


class TestGetTenantContext:
    """Tests for the get_tenant_context dependency."""

    async def test_missing_tenant_id(self):
        """Test that missing X-Tenant-ID raises 401."""
        request = make_mock_request({
            "X-Platform": "freshdesk",
            "X-API-Key": "key",
        })
        
        with pytest.raises(HTTPException) as exc:
            await get_tenant_context(request)
        
        assert exc.value.status_code == 401
        assert "X-Tenant-ID" in exc.value.detail

    async def test_missing_platform(self):
        """Test that missing X-Platform raises 401."""
        request = make_mock_request({
            "X-Tenant-ID": "wedosoft",
            "X-API-Key": "key",
        })
        
        with pytest.raises(HTTPException) as exc:
            await get_tenant_context(request)
        
        assert exc.value.status_code == 401
        assert "X-Platform" in exc.value.detail

    async def test_unsupported_platform(self):
        """Test that unsupported platform raises 400."""
        request = make_mock_request({
            "X-Tenant-ID": "wedosoft",
            "X-Platform": "unknown_platform",
            "X-API-Key": "key",
        })
        
        with pytest.raises(HTTPException) as exc:
            await get_tenant_context(request)
        
        assert exc.value.status_code == 400
        assert "Unsupported platform" in exc.value.detail

    async def test_missing_api_key(self):
        """Test that missing X-API-Key raises 401."""
        request = make_mock_request({
            "X-Tenant-ID": "wedosoft",
            "X-Platform": "freshdesk",
        })
        
        with pytest.raises(HTTPException) as exc:
            await get_tenant_context(request)
        
        assert exc.value.status_code == 401
        assert "X-API-Key" in exc.value.detail

    async def test_invalid_api_key(self):
        """Test that invalid API key raises 403."""
        request = make_mock_request({
            "X-Tenant-ID": "wedosoft",
            "X-Platform": "freshdesk",
            "X-API-Key": "invalid",
            "X-Domain": "wedosoft.freshdesk.com",
        })
        
        with patch("app.middleware.tenant_auth.verify_platform_api_key", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await get_tenant_context(request)
            
            assert exc.value.status_code == 403

    async def test_valid_request(self):
        """Test successful tenant context creation."""
        request = make_mock_request({
            "X-Tenant-ID": "wedosoft",
            "X-Platform": "freshdesk",
            "X-API-Key": "valid_key",
            "X-Domain": "wedosoft.freshdesk.com",
        })
        
        with patch("app.middleware.tenant_auth.verify_platform_api_key", return_value=True):
            context = await get_tenant_context(request)
            
            assert context.tenant_id == "wedosoft"
            assert context.platform == "freshdesk"
            assert context.verified is True
            assert len(context.mandatory_filters) == 2


class TestOptionalTenantContext:
    """Tests for optional tenant context."""

    async def test_no_headers_returns_none(self):
        """Test that missing headers returns None instead of error."""
        request = make_mock_request({})
        
        context = await get_optional_tenant_context(request)
        
        assert context is None

    async def test_partial_headers_returns_none(self):
        """Test that partial headers returns None."""
        request = make_mock_request({"X-Tenant-ID": "wedosoft"})
        
        context = await get_optional_tenant_context(request)
        
        assert context is None


class TestSupportedPlatforms:
    """Tests for platform support."""

    def test_freshdesk_supported(self):
        assert "freshdesk" in SUPPORTED_PLATFORMS

    def test_zendesk_supported(self):
        assert "zendesk" in SUPPORTED_PLATFORMS

    def test_web_supported(self):
        assert "web" in SUPPORTED_PLATFORMS

    def test_api_supported(self):
        assert "api" in SUPPORTED_PLATFORMS
