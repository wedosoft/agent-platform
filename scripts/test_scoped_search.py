import asyncio
import os
import logging
import sys

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.gemini_file_search_client import GeminiFileSearchClient
from app.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    settings = get_settings()
    api_key = settings.gemini_api_key
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found")
        return

    client = GeminiFileSearchClient(
        api_key=api_key,
        primary_model=settings.gemini_primary_model
    )

    # 1. Search Tickets Only
    tickets_store = settings.gemini_store_tickets
    if tickets_store:
        print("\n=== 1. Searching Tickets Only (sources=['tickets']) ===")
        query = "김민정이 제출한 티켓"
        try:
            result = await client.search(
                query=query,
                store_names=[tickets_store],
                metadata_filters=None
            )
            print(f"Query: {query}")
            text = result.get('text') or ""
            print(f"Result Text: {text[:100]}...")
            print(f"Chunks: {len(result.get('grounding_chunks', []))}")
        except Exception as e:
            print(f"Error: {e}")

    # 2. Search Articles Only
    articles_store = settings.gemini_store_articles
    if articles_store:
        print("\n=== 2. Searching Articles Only (sources=['articles']) ===")
        query = "비밀번호 재설정 방법" # Assuming this might be in articles
        try:
            result = await client.search(
                query=query,
                store_names=[articles_store],
                metadata_filters=None
            )
            print(f"Query: {query}")
            text = result.get('text') or ""
            print(f"Result Text: {text[:100]}...")
            print(f"Chunks: {len(result.get('grounding_chunks', []))}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
