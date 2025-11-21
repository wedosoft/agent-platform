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


class TenantConfig(BaseModel):
    id: str
    product: str
    pipeline_type: Literal["freshdesk_rag", "langgraph", "external"] = "freshdesk_rag"
    metadata_filters: List[TenantMetadataFilter] = Field(default_factory=list)
    gemini: TenantGeminiConfig = Field(default_factory=TenantGeminiConfig)

    def build_metadata_filters(self) -> List[MetadataFilter]:
        return [item.to_dataclass() for item in self.metadata_filters]
