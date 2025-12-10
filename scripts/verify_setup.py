import sys
import os
import asyncio

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.repositories.proposal_repository import get_proposal_repository

async def main():
    print("Verifying setup...")
    settings = get_settings()
    print(f"Redis URL: {settings.redis_url}")
    
    repo = get_proposal_repository()
    print(f"Repository initialized. Redis client: {repo.redis}")
    
    if repo.redis:
        try:
            await repo.redis.ping()
            print("Redis connection successful!")
        except Exception as e:
            print(f"Redis connection failed: {e}")
    else:
        print("Using in-memory storage.")

if __name__ == "__main__":
    asyncio.run(main())
