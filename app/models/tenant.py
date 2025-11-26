from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.metadata import MetadataFilter, MetadataOperator


class TenantMetadataFilter(BaseModel):
    key: str
    value: str
    operator: MetadataOperator = "EQUALS"

    def to_dataclass(self) -> MetadataFilter:
        return MetadataFilter(key=self.key, value=self.value, operator=self.operator)


class TenantGeminiConfig(BaseModel):
    store_names: List[str] = Field(default_factory=list)
    default_store: Optional[str] = None


class TenantPlatformConfig(BaseModel):
    """Platform-specific configuration for a tenant."""
    enabled: bool = True
    domain: Optional[str] = None  # e.g., 'wedosoft.freshdesk.com'
    api_key_hash: Optional[str] = None  # Hashed API key for verification (optional)
    custom_store: Optional[str] = None  # Platform-specific store override


class TenantConfig(BaseModel):
    id: str
    product: str
    pipeline_type: Literal["freshdesk_rag", "langgraph", "external"] = "freshdesk_rag"
    metadata_filters: List[TenantMetadataFilter] = Field(default_factory=list)
    gemini: TenantGeminiConfig = Field(default_factory=TenantGeminiConfig)
    
    # Multitenant platform configurations
    platforms: dict[str, TenantPlatformConfig] = Field(default_factory=dict)
    
    # Shared store configuration
    use_shared_stores: bool = True  # If True, use shared stores with tenant_id filter
    
    def build_metadata_filters(self) -> List[MetadataFilter]:
        return [item.to_dataclass() for item in self.metadata_filters]

    def get_platform_config(self, platform: str) -> Optional[TenantPlatformConfig]:
        """Get configuration for a specific platform."""
        return self.platforms.get(platform)

    def is_platform_enabled(self, platform: str) -> bool:
        """Check if a platform is enabled for this tenant."""
        config = self.platforms.get(platform)
        return config.enabled if config else True  # Default to enabled

    def get_effective_store(self, platform: str) -> Optional[str]:
        """Get the effective store for a platform (custom or default)."""
        platform_config = self.platforms.get(platform)
        if platform_config and platform_config.custom_store:
            return platform_config.custom_store
        return self.gemini.default_store

