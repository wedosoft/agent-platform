"""
Redis Proposal Repository
Handles persistence of proposals using Redis
"""
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ProposalRepository:
    def __init__(self):
        self.settings = get_settings()
        self.redis = None
        self._memory_store = {}  # Always initialize memory store as fallback
        
        if self.settings.redis_url:
            try:
                self.redis = redis.from_url(self.settings.redis_url, decode_responses=True)
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {e}")
                self.redis = None
        
        if not self.redis:
            logger.warning("Redis not available, using in-memory dict for proposals (not persistent)")

    async def save_proposal(self, proposal_id: str, data: Dict[str, Any], ttl_seconds: int = 86400):
        if self.redis:
            try:
                await self.redis.setex(f"proposal:{proposal_id}", ttl_seconds, json.dumps(data))
                return
            except Exception as e:
                logger.error(f"Redis save failed, falling back to memory: {e}")
                self.redis = None # Disable Redis for future calls
        
        # Fallback
        self._memory_store[proposal_id] = data

    async def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        if self.redis:
            try:
                data = await self.redis.get(f"proposal:{proposal_id}")
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Redis get failed, falling back to memory: {e}")
                self.redis = None # Disable Redis for future calls
        
        # Fallback
        return self._memory_store.get(proposal_id)

_repo_instance = None

async def get_proposal_repository() -> ProposalRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = ProposalRepository()
    return _repo_instance
