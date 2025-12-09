"""
Freshdesk 데이터 수집 서비스 - 고성능 병렬 수집

TypeScript google-file-saerch-tool/src/lib/pipeline/ingestion-service.ts 완전 포팅
- Worker 패턴으로 대화 병렬 수집
- asyncio.Semaphore로 동시성 제어
- 대량 데이터 고속 처리
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator

from app.services.freshdesk_client import FreshdeskClient, FreshdeskClientError

logger = logging.getLogger(__name__)


@dataclass
class TicketIngestionRecord:
    """티켓 + 대화 수집 레코드"""
    ticket: Dict[str, Any]
    conversations: List[Dict[str, Any]]


@dataclass
class IngestionOptions:
    """수집 옵션"""
    per_page: int = 100
    conversation_concurrency: int = 10  # 대화 병렬 수집 동시성
    rate_limit_delay_ms: int = 100
    include_conversations: bool = True
    include_description: bool = True


class FreshdeskIngestionService:
    """
    Freshdesk 데이터 고속 수집 서비스
    
    TypeScript의 Worker 패턴을 Python asyncio로 구현:
    - 티켓 페이지네이션 수집
    - 대화 병렬 첨부 (N개 동시 요청)
    - 아티클 카테고리/폴더 순회
    """
    
    def __init__(
        self,
        client: FreshdeskClient,
        options: Optional[IngestionOptions] = None
    ):
        self.client = client
        self.options = options or IngestionOptions()
        
        # 캐시
        self._contacts_cache: Dict[int, Dict[str, Any]] = {}
        self._agents_cache: Dict[int, Dict[str, Any]] = {}
    
    async def fetch_tickets(
        self,
        *,
        since: Optional[datetime] = None,
        include_conversations: Optional[bool] = None,
        conversation_concurrency: Optional[int] = None,
        per_page: Optional[int] = None,
        include_fields: Optional[List[str]] = None
    ) -> List[TicketIngestionRecord]:
        """
        티켓 + 대화 수집
        
        Args:
            since: 증분 동기화 시작점 (updated_since)
            include_conversations: 대화 포함 여부 (기본 True)
            conversation_concurrency: 대화 병렬 수집 동시성
            per_page: 페이지당 티켓 수
            include_fields: 추가 필드 (description, requester 등)
        
        Returns:
            티켓 + 대화 레코드 리스트
        """
        _per_page = per_page or self.options.per_page
        _include_conversations = (
            include_conversations 
            if include_conversations is not None 
            else self.options.include_conversations
        )
        _concurrency = conversation_concurrency or self.options.conversation_concurrency
        
        # 추가 필드 결정
        _include_fields = list(include_fields or [])
        if self.options.include_description and "description" not in _include_fields:
            _include_fields.append("description")
        
        logger.info(f"Fetching tickets (since={since}, concurrency={_concurrency})")
        
        # 1. 전체 티켓 수집 (페이지네이션)
        tickets = await self._fetch_all_tickets(
            since=since,
            per_page=_per_page,
            include_fields=_include_fields or None,
        )
        
        logger.info(f"Fetched {len(tickets)} tickets")
        
        if not tickets:
            return []
        
        # 2. 대화 병렬 첨부
        if _include_conversations:
            records = await self._attach_conversations(tickets, _concurrency)
        else:
            records = [
                TicketIngestionRecord(ticket=t, conversations=[]) 
                for t in tickets
            ]
        
        total_conversations = sum(len(r.conversations) for r in records)
        logger.info(f"Attached {total_conversations} conversations to {len(records)} tickets")
        
        return records

    async def fetch_tickets_generator(
        self,
        *,
        since: Optional[datetime] = None,
        include_conversations: Optional[bool] = None,
        conversation_concurrency: Optional[int] = None,
        per_page: Optional[int] = None,
        include_fields: Optional[List[str]] = None
    ) -> AsyncGenerator[List[TicketIngestionRecord], None]:
        """
        티켓 + 대화 수집 (제너레이터 방식 - 배치 처리용)
        """
        _per_page = per_page or self.options.per_page
        _include_conversations = (
            include_conversations 
            if include_conversations is not None 
            else self.options.include_conversations
        )
        _concurrency = conversation_concurrency or self.options.conversation_concurrency
        
        # 추가 필드 결정
        _include_fields = list(include_fields or [])
        if self.options.include_description and "description" not in _include_fields:
            _include_fields.append("description")
        
        logger.info(f"Fetching tickets generator (since={since}, concurrency={_concurrency})")
        
        page = 1
        while True:
            # 1. 페이지 단위 티켓 수집
            tickets = await self.client.get_tickets(
                page=page,
                per_page=_per_page,
                updated_since=since,
                include_fields=_include_fields or None,
            )
            
            if not tickets:
                break
            
            logger.info(f"Fetched page {page}: {len(tickets)} tickets")
            
            # 2. 대화 병렬 첨부
            if _include_conversations:
                records = await self._attach_conversations(tickets, _concurrency)
            else:
                records = [
                    TicketIngestionRecord(ticket=t, conversations=[]) 
                    for t in tickets
                ]
            
            yield records
            
            if len(tickets) < _per_page:
                break
                
            page += 1
    
    async def fetch_articles(
        self,
        *,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        전체 아티클 수집
        
        Args:
            since: 증분 동기화 시작점
        
        Returns:
            아티클 리스트 (카테고리/폴더 정보 포함)
        """
        logger.info(f"Fetching articles (since={since})")
        return await self.client.get_all_articles(updated_since=since)
    
    async def _fetch_all_tickets(
        self,
        *,
        since: Optional[datetime] = None,
        per_page: int = 100,
        include_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """전체 티켓 수집 (페이지네이션)"""
        return await self.client.get_all_tickets(
            updated_since=since,
            per_page=per_page,
            include_fields=include_fields,
        )
    
    async def _attach_conversations(
        self,
        tickets: List[Dict[str, Any]],
        concurrency: int
    ) -> List[TicketIngestionRecord]:
        """
        대화 병렬 첨부 (Worker 패턴)
        
        TypeScript의 attachConversations() 직접 포팅:
        - 공유 커서 + 워커 풀로 N개 동시 요청
        - 실패해도 빈 대화로 계속 진행
        """
        if not tickets:
            return []
        
        max_concurrency = max(1, min(concurrency, len(tickets)))
        results: List[Optional[TicketIngestionRecord]] = [None] * len(tickets)
        cursor = 0
        lock = asyncio.Lock()
        
        async def worker():
            nonlocal cursor
            
            while True:
                # 다음 작업 인덱스 획득 (원자적)
                async with lock:
                    if cursor >= len(tickets):
                        return
                    current_index = cursor
                    cursor += 1
                
                ticket = tickets[current_index]
                ticket_id = ticket.get("id")
                
                if ticket_id is None:
                    results[current_index] = TicketIngestionRecord(
                        ticket=ticket,
                        conversations=[]
                    )
                    continue
                
                try:
                    conversations = await self.client.get_all_conversations(int(ticket_id))
                    results[current_index] = TicketIngestionRecord(
                        ticket=ticket,
                        conversations=conversations
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch conversations for ticket {ticket_id}: {e}")
                    results[current_index] = TicketIngestionRecord(
                        ticket=ticket,
                        conversations=[]
                    )
        
        # 워커 풀 실행
        workers = [asyncio.create_task(worker()) for _ in range(max_concurrency)]
        await asyncio.gather(*workers)
        
        # None 필터링 (정상적으로는 없어야 함)
        return [r for r in results if r is not None]
    
    async def fetch_contacts_for_ids(
        self,
        contact_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        연락처 ID 목록으로 연락처 조회 (캐시 사용)
        
        Args:
            contact_ids: 연락처 ID 리스트
        
        Returns:
            연락처 정보 리스트
        """
        unique_ids = list(set(cid for cid in contact_ids if cid is not None))
        missing_ids = [cid for cid in unique_ids if cid not in self._contacts_cache]
        
        if missing_ids:
            await self._fetch_entities_by_ids(
                ids=missing_ids,
                cache=self._contacts_cache,
                fetcher=self.client.get_contact,
                entity_label="contact"
            )
        
        return [
            self._contacts_cache[cid]
            for cid in unique_ids
            if cid in self._contacts_cache
        ]
    
    async def fetch_agents_for_ids(
        self,
        agent_ids: List[Optional[int]]
    ) -> List[Dict[str, Any]]:
        """
        에이전트 ID 목록으로 에이전트 조회 (캐시 사용)
        """
        unique_ids = list(set(aid for aid in agent_ids if aid is not None))
        missing_ids = [aid for aid in unique_ids if aid not in self._agents_cache]
        
        if missing_ids:
            await self._fetch_entities_by_ids(
                ids=missing_ids,
                cache=self._agents_cache,
                fetcher=self.client.get_agent,
                entity_label="agent"
            )
        
        return [
            self._agents_cache[aid]
            for aid in unique_ids
            if aid in self._agents_cache
        ]
    
    async def _fetch_entities_by_ids(
        self,
        ids: List[int],
        cache: Dict[int, Dict[str, Any]],
        fetcher,
        entity_label: str
    ) -> None:
        """
        엔티티 병렬 조회 (Worker 패턴)
        """
        if not ids:
            return
        
        concurrency = min(self.options.conversation_concurrency, len(ids))
        cursor = 0
        lock = asyncio.Lock()
        
        async def worker():
            nonlocal cursor
            
            while True:
                async with lock:
                    if cursor >= len(ids):
                        return
                    current_id = ids[cursor]
                    cursor += 1
                
                try:
                    entity = await fetcher(current_id)
                    if entity:
                        cache[current_id] = entity
                except FreshdeskClientError as e:
                    if "404" in str(e):
                        logger.debug(f"Skipping {entity_label} {current_id}: not found")
                    else:
                        logger.warning(f"Failed to fetch {entity_label} {current_id}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to fetch {entity_label} {current_id}: {e}")
                
                # Rate limit 방지
                await asyncio.sleep(self.options.rate_limit_delay_ms / 1000.0)
        
        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)


def create_ingestion_service(
    client: FreshdeskClient,
    *,
    conversation_concurrency: int = 10,
    per_page: int = 100
) -> FreshdeskIngestionService:
    """IngestionService 팩토리 함수"""
    options = IngestionOptions(
        per_page=per_page,
        conversation_concurrency=conversation_concurrency,
    )
    return FreshdeskIngestionService(client, options)
