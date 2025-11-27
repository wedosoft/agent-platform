"""
Freshdesk Entity Mapper
Handles all ID-to-Label mappings (agents, groups, companies, contacts, etc.)
Based on TypeScript entity-mapper.ts implementation

Features:
- Batch entity caching (agents, groups, products, categories, ticket_fields)
- On-demand entity loading (companies, contacts, folders)
- Field choices mapping (status, priority, source, type)
- TTL-based cache expiration
- LRU eviction on size limit
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.services.freshdesk_client import FreshdeskClient

logger = logging.getLogger(__name__)


@dataclass
class EntityCache:
    """Entity ID → Label 캐시"""
    data: dict[int, str] = field(default_factory=dict)
    expires_at: datetime | None = None

    def is_valid(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now() < self.expires_at


@dataclass
class FieldChoices:
    """티켓 필드 choices 캐시 (status, priority, source, type)"""
    status: dict[int, str] = field(default_factory=dict)
    priority: dict[int, str] = field(default_factory=dict)
    source: dict[int, str] = field(default_factory=dict)
    type: dict[int, str] = field(default_factory=dict)


class EntityMapper:
    """
    Freshdesk Entity Mapper
    
    Usage:
        client = FreshdeskClient(domain, api_key)
        mapper = EntityMapper(client)
        await mapper.initialize()
        
        # Get agent label
        label = await mapper.get_label("agents", 12345)
        
        # Map ticket entities
        entities = await mapper.map_ticket_entities(ticket)
    """
    
    # 배치 로드 엔티티 (초기화 시 한번에 로드)
    BATCH_ENTITIES = ["agents", "groups", "products", "categories", "ticket_fields"]
    
    # 온디맨드 엔티티 (필요 시 개별 로드)
    ON_DEMAND_ENTITIES = ["companies", "contacts", "folders"]
    
    # 캐시 설정
    CACHE_TTL_SECONDS = 3600  # 1 hour
    MAX_CACHE_SIZE = 10000
    
    def __init__(self, client: FreshdeskClient):
        self.client = client
        self._cache: dict[str, EntityCache] = {}
        self._field_choices = FieldChoices()
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """
        Initialize - Load batch entities in parallel
        """
        logger.info("EntityMapper 초기화 시작...")
        
        tasks = [
            self._load_entity(entity_type)
            for entity_type in self.BATCH_ENTITIES
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for entity_type, result in zip(self.BATCH_ENTITIES, results):
            if isinstance(result, Exception):
                logger.error(f"{entity_type} 로드 실패: {result}")
        
        logger.info(f"EntityMapper 초기화 완료: {self.get_stats()}")
    
    async def _load_entity(self, entity_type: str) -> bool:
        """
        Load entity data and cache it
        """
        # 캐시 유효성 검사
        if entity_type in self._cache and self._cache[entity_type].is_valid():
            return True
        
        try:
            data: list[dict[str, Any]] = []
            
            if entity_type == "agents":
                data = await self.client.get_all_agents()
            elif entity_type == "groups":
                data = await self.client.get_all_groups()
            elif entity_type == "products":
                data = await self.client.get_all_products()
            elif entity_type == "categories":
                data = await self.client.get_all_categories()
            elif entity_type == "folders":
                data = await self._load_folders()
            elif entity_type == "ticket_fields":
                await self._load_ticket_fields()
                return True
            else:
                logger.error(f"알 수 없는 엔티티 타입: {entity_type}")
                return False
            
            self._cache_entity(entity_type, data)
            logger.info(f"{entity_type} 로드 완료: {len(data)}개")
            return True
            
        except Exception as e:
            logger.error(f"{entity_type} 로드 중 오류: {e}")
            return False
    
    async def _load_folders(self) -> list[dict[str, Any]]:
        """
        Load folders (requires categories first)
        """
        # 카테고리 먼저 로드
        if "categories" not in self._cache or not self._cache["categories"].is_valid():
            await self._load_entity("categories")
        
        all_folders: list[dict[str, Any]] = []
        category_ids = list(self._cache.get("categories", EntityCache()).data.keys())
        
        for category_id in category_ids:
            try:
                folders = await self.client.get_folders_for_category(category_id)
                all_folders.extend(folders)
            except Exception as e:
                logger.warning(f"카테고리 {category_id}의 폴더 로드 실패: {e}")
        
        return all_folders
    
    async def _load_ticket_fields(self) -> None:
        """
        Load ticket fields (status, priority, source, type choices)
        Uses /api/v2/ticket_fields API
        
        Each field has different choices structure:
        - status: { "2": ["Open", "처리 중입니다."], "3": ["Pending", ...] }
        - priority: { "Low": 1, "Medium": 2, ... } (reversed!)
        - source: { "Email": 1, "Portal": 2, ... } (reversed!)
        - ticket_type: ["Question", "Incident", ...] (array)
        """
        try:
            ticket_fields = await self.client.get_ticket_fields()
            
            for field_data in ticket_fields:
                field_name = (field_data.get("name") or "").lower()
                choices = field_data.get("choices")
                
                if not choices:
                    continue
                
                if field_name in ("status", "ticket_status"):
                    # status: {"2": ["Open", "처리 중입니다."], ...}
                    # Key is ID (string), value is array where first element is label
                    self._field_choices.status = {}
                    if isinstance(choices, dict):
                        for id_str, label_array in choices.items():
                            try:
                                num_id = int(id_str)
                                if isinstance(label_array, list) and label_array:
                                    self._field_choices.status[num_id] = str(label_array[0])
                            except (ValueError, TypeError):
                                continue
                
                elif field_name == "priority":
                    # priority: {"Low": 1, "Medium": 2, ...} (reversed!)
                    self._field_choices.priority = {}
                    if isinstance(choices, dict):
                        for label, id_val in choices.items():
                            try:
                                num_id = int(id_val)
                                self._field_choices.priority[num_id] = str(label)
                            except (ValueError, TypeError):
                                continue
                
                elif field_name == "source":
                    # source: {"Email": 1, "Portal": 2, ...} (reversed!)
                    self._field_choices.source = {}
                    if isinstance(choices, dict):
                        for label, id_val in choices.items():
                            try:
                                num_id = int(id_val)
                                self._field_choices.source[num_id] = str(label)
                            except (ValueError, TypeError):
                                continue
                
                elif field_name in ("ticket_type", "type"):
                    # ticket_type: ["Question", "Incident", ...] (array)
                    self._field_choices.type = {}
                    if isinstance(choices, list):
                        for idx, label in enumerate(choices):
                            if isinstance(label, str):
                                self._field_choices.type[idx + 1] = label
            
            logger.info(
                "ticket_fields 로드 완료: "
                f"status={len(self._field_choices.status)}, "
                f"priority={len(self._field_choices.priority)}, "
                f"source={len(self._field_choices.source)}, "
                f"type={len(self._field_choices.type)}"
            )
            
        except Exception as e:
            logger.error(f"ticket_fields 로드 실패: {e}")
    
    def _cache_entity(self, entity_type: str, data: list[dict[str, Any]]) -> None:
        """
        Cache entity data with ID → Label mapping
        """
        # 캐시 크기 제한 확인
        total_items = sum(len(cache.data) for cache in self._cache.values())
        
        if total_items > self.MAX_CACHE_SIZE:
            logger.warning(f"캐시 크기 제한 도달: {total_items} > {self.MAX_CACHE_SIZE}")
            # 가장 오래된 캐시 삭제
            if self._cache:
                oldest_entity = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].expires_at or datetime.min
                )
                del self._cache[oldest_entity]
                logger.info(f"오래된 캐시 삭제: {oldest_entity}")
        
        # ID → Label 매핑 생성
        mapping: dict[int, str] = {}
        
        if entity_type == "agents":
            for agent in data:
                name = ""
                if "contact" in agent and agent["contact"]:
                    name = agent["contact"].get("name", "")
                if not name:
                    name = agent.get("name", "")
                if agent.get("id"):
                    mapping[agent["id"]] = name
        
        elif entity_type == "groups":
            for group in data:
                if group.get("id"):
                    mapping[group["id"]] = group.get("name", "")
        
        elif entity_type == "companies":
            for company in data:
                if company.get("id"):
                    mapping[company["id"]] = company.get("name", "")
        
        elif entity_type == "products":
            for product in data:
                if product.get("id"):
                    mapping[product["id"]] = product.get("name", "")
        
        elif entity_type == "contacts":
            for contact in data:
                if contact.get("id"):
                    mapping[contact["id"]] = contact.get("name", "")
        
        elif entity_type == "categories":
            for category in data:
                if category.get("id"):
                    mapping[category["id"]] = category.get("name", "")
        
        elif entity_type == "folders":
            for folder in data:
                if folder.get("id"):
                    mapping[folder["id"]] = folder.get("name", "")
        
        self._cache[entity_type] = EntityCache(
            data=mapping,
            expires_at=datetime.now() + timedelta(seconds=self.CACHE_TTL_SECONDS)
        )
    
    def get_field_label(
        self, 
        field_type: str, 
        field_id: int | None
    ) -> str | None:
        """
        Get field choice label (status, priority, source, type)
        """
        if field_id is None:
            return None
        
        choices = getattr(self._field_choices, field_type, {})
        return choices.get(field_id)
    
    def get_field_choices(self, field_type: str) -> dict[int, str]:
        """
        Get all field choices for a field type
        """
        return getattr(self._field_choices, field_type, {})
    
    async def get_label(
        self, 
        entity_type: str, 
        entity_id: int | None
    ) -> str:
        """
        Get label for entity ID
        """
        if entity_id is None:
            return ""
        
        # 캐시 확인
        cache = self._cache.get(entity_type)
        if not cache or not cache.is_valid():
            # 배치 엔티티는 리로드
            if entity_type in self.BATCH_ENTITIES:
                await self._load_entity(entity_type)
            # 온디맨드 엔티티는 개별 조회
            elif entity_type in self.ON_DEMAND_ENTITIES:
                return await self._get_single_entity_label(entity_type, entity_id)
        
        # 캐시에서 가져오기
        cache = self._cache.get(entity_type)
        if cache and entity_id in cache.data:
            return cache.data[entity_id]
        
        return str(entity_id)
    
    async def _get_single_entity_label(
        self, 
        entity_type: str, 
        entity_id: int
    ) -> str:
        """
        Get single entity label (for companies, contacts)
        """
        # 캐시 먼저 확인
        cache = self._cache.get(entity_type)
        if cache and entity_id in cache.data:
            return cache.data[entity_id]
        
        try:
            data = None
            
            if entity_type == "companies":
                data = await self.client.get_company(entity_id)
            elif entity_type == "contacts":
                data = await self.client.get_contact(entity_id)
            
            if not data:
                return str(entity_id)
            
            label = data.get("name") or str(entity_id)
            
            # 캐시에 추가
            if entity_type not in self._cache:
                self._cache[entity_type] = EntityCache()
            self._cache[entity_type].data[entity_id] = label
            
            return label
            
        except Exception as e:
            logger.warning(f"{entity_type} {entity_id} 조회 실패: {e}")
            return str(entity_id)
    
    async def get_requester_label(self, requester_id: int | None) -> str:
        """
        Get requester label (contact or agent)
        """
        if requester_id is None:
            return ""
        
        # 먼저 contact 시도
        try:
            contact = await self.client.get_contact(requester_id)
            if contact and contact.get("name"):
                # 캐시에 추가
                if "contacts" not in self._cache:
                    self._cache["contacts"] = EntityCache()
                self._cache["contacts"].data[requester_id] = contact["name"]
                return contact["name"]
        except Exception:
            pass
        
        # contact 실패 시 agent 시도
        agent_label = await self.get_label("agents", requester_id)
        if agent_label and agent_label != str(requester_id):
            return agent_label
        
        return str(requester_id)
    
    async def map_ticket_entities(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """
        Map ticket entities to labels
        
        Returns:
            {
                "responder_id": int | None,
                "responder_label": str,
                "group_id": int | None,
                "group_label": str,
                "company_id": int | None,
                "company_label": str,
                "requester_id": int | None,
                "requester_label": str,
                "product_id": int | None,
                "product_label": str,
            }
        """
        # 병렬로 라벨 조회
        responder_label, group_label, company_label, requester_label, product_label = await asyncio.gather(
            self.get_label("agents", ticket.get("responder_id")),
            self.get_label("groups", ticket.get("group_id")),
            self.get_label("companies", ticket.get("company_id")),
            self.get_requester_label(ticket.get("requester_id")),
            self.get_label("products", ticket.get("product_id")),
        )
        
        return {
            "responder_id": ticket.get("responder_id"),
            "responder_label": responder_label,
            "group_id": ticket.get("group_id"),
            "group_label": group_label,
            "company_id": ticket.get("company_id"),
            "company_label": company_label,
            "requester_id": ticket.get("requester_id"),
            "requester_label": requester_label,
            "product_id": ticket.get("product_id"),
            "product_label": product_label,
        }
    
    async def map_article_entities(self, article: dict[str, Any]) -> dict[str, Any]:
        """
        Map article entities to labels
        
        Returns:
            {
                "category_id": int | None,
                "category_label": str,
                "folder_id": int | None,
                "folder_label": str,
            }
        """
        category_label, folder_label = await asyncio.gather(
            self.get_label("categories", article.get("category_id")),
            self.get_label("folders", article.get("folder_id")),
        )
        
        return {
            "category_id": article.get("category_id"),
            "category_label": category_label,
            "folder_id": article.get("folder_id"),
            "folder_label": folder_label,
        }
    
    def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics
        """
        return {
            entity_type: len(cache.data)
            for entity_type, cache in self._cache.items()
        }
