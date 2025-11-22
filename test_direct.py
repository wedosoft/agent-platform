import asyncio
import json
import logging
from app.services.gemini_file_search_client import GeminiFileSearchClient
from app.services.common_chat_handler import CommonChatHandler
from app.models.session import ChatRequest

logging.basicConfig(level=logging.INFO)

async def test():
    client = GeminiFileSearchClient(
        api_key="AIzaSyDClNvAU1WSF2_ajlTbvA0VtB-fs0k8nXU",
        primary_model="gemini-2.5-flash",
        fallback_model="gemini-pro-latest"
    )
    
    handler = CommonChatHandler(
        gemini_client=client,
        store_name="fileSearchStores/freshworkskb20251122-yri7eholu2qr",
        documents_service=None
    )
    
    request = ChatRequest(
        query="워크플로우 자동화",
        sessionId="test-direct",
        sources=["fileSearchStores/freshworkskb20251122-yri7eholu2qr"],
        common_product="freshservice"
    )
    
    result = await handler.handle(request)
    print("\n" + "="*80)
    print("RESULT:")
    print(json.dumps(result.dict(), ensure_ascii=False, indent=2))

asyncio.run(test())
