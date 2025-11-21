from app.models.session import ChatRequest
from app.models.tenant import TenantConfig, TenantGeminiConfig, TenantMetadataFilter
from app.services.agent_chat_service import AgentChatService
from app.models.metadata import MetadataFilter


class _DummyGeminiClient:
    async def search(self, **kwargs):  # pragma: no cover - not used in these unit tests
        return {}


class _DummyAnalyzer:
    async def analyze(self, *args, **kwargs):  # pragma: no cover - not used
        return None


def _build_service() -> AgentChatService:
    return AgentChatService(
        gemini_client=_DummyGeminiClient(),
        analyzer=_DummyAnalyzer(),
        freshdesk_search=None,
    )


def _build_tenant(product: str = "freshservice") -> TenantConfig:
    return TenantConfig(
        id="freshservice-sk",
        product=product,
        pipeline_type="freshdesk_rag",
        metadata_filters=[
            TenantMetadataFilter(key="product", value=product, operator="EQUALS"),
            TenantMetadataFilter(key="docType", value="playbook", operator="EQUALS"),
        ],
        gemini=TenantGeminiConfig(store_names=["store-a"], default_store="store-a"),
    )


def test_metadata_filters_override_with_request_product():
    service = _build_service()
    tenant = _build_tenant()
    request = ChatRequest(sessionId="abc123", query="무엇을 도와드릴까요?", commonProduct="custom-product")

    filters = service._build_metadata_filters(
        tenant=tenant,
        request=request,
        analyzer_filters=[MetadataFilter(key="priority", value="4", operator="EQUALS")],
    )

    product_filters = [f for f in filters if f.key == "product"]
    assert product_filters, "요청 기반 제품 필터가 존재해야 합니다"
    assert product_filters[0].value == "custom-product"
    assert any(f.key == "docType" for f in filters), "기존 테넌트 필터가 유지되어야 합니다"
    assert filters[-1].key == "priority", "분석기 필터가 마지막에 유지되어야 합니다"


def test_filter_summaries_use_request_product_first():
    service = _build_service()
    tenant = _build_tenant(product="default-product")
    request = ChatRequest(sessionId="session", query="query", commonProduct="selected-product")

    summaries = service._build_filter_summaries(
        tenant=tenant,
        request=request,
        analyzer_summaries=["우선순위=긴급"],
    )

    assert summaries[0] == "제품=selected-product"
    assert "우선순위=긴급" in summaries