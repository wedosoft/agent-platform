"""
Freshdesk Normalizer
Handles normalization of tickets, conversations, and articles
Converts numeric IDs to human-readable labels (status, priority, source, etc.)

Based on TypeScript normalizer.ts implementation

Features:
- Ticket/Article/Conversation normalization
- Status/Priority/Source number → string conversion
- Entity label lookup from cache
- Custom field normalization
- EntityMapper integration for labels
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Freshdesk Enums
# ============================================================================

class TicketStatus(IntEnum):
    """Freshdesk 티켓 상태"""
    OPEN = 2
    PENDING = 3
    RESOLVED = 4
    CLOSED = 5


class TicketPriority(IntEnum):
    """Freshdesk 티켓 우선순위"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TicketSource(IntEnum):
    """Freshdesk 티켓 소스"""
    EMAIL = 1
    PORTAL = 2
    PHONE = 3
    CHAT = 7
    FEEDBACK = 9
    OUTBOUND = 10


class ArticleStatus(IntEnum):
    """Freshdesk 아티클 상태"""
    DRAFT = 1
    PUBLISHED = 2


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class NormalizerCache:
    """ID → Label 캐시"""
    contacts: dict[int, str] = field(default_factory=dict)
    agents: dict[int, str] = field(default_factory=dict)
    groups: dict[int, str] = field(default_factory=dict)
    products: dict[int, str] = field(default_factory=dict)
    categories: dict[int, str] = field(default_factory=dict)
    folders: dict[int, str] = field(default_factory=dict)


@dataclass
class FieldMappings:
    """필드 매핑 (EntityMapper에서 로드)"""
    status: dict[int, str] = field(default_factory=dict)
    priority: dict[int, str] = field(default_factory=dict)
    source: dict[int, str] = field(default_factory=dict)
    type: dict[int, str] = field(default_factory=dict)
    custom_fields: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class NormalizedTicket:
    """정규화된 티켓"""
    id: int
    subject: str
    description_text: str
    status: str
    priority: str
    source: str
    type: str | None
    requester: str
    requester_id: int
    responder: str | None
    responder_id: int | None
    group: str | None
    group_id: int | None
    product: str | None
    product_id: int | None
    tags: list[str]
    created_at: str
    updated_at: str
    due_by: str | None
    fr_due_by: str | None
    custom_fields: dict[str, Any] | None = None
    conversations: list["NormalizedConversation"] | None = None


@dataclass
class NormalizedConversation:
    """정규화된 대화"""
    id: int
    body_text: str
    from_email: str | None
    to_emails: list[str] | None
    user_name: str
    incoming: bool
    private: bool
    created_at: str
    updated_at: str
    attachments: list[dict[str, Any]] | None = None


@dataclass
class NormalizedArticle:
    """정규화된 아티클"""
    id: int
    title: str
    description_text: str
    status: str
    category: str
    category_id: int
    folder: str
    folder_id: int
    tags: list[str]
    seo_data: dict[str, Any] | None
    created_at: str
    updated_at: str


# ============================================================================
# Normalizer Class
# ============================================================================

class FreshdeskNormalizer:
    """
    Freshdesk Normalizer
    
    Converts raw Freshdesk API responses to normalized format
    with human-readable labels for IDs.
    
    Usage:
        normalizer = FreshdeskNormalizer()
        
        # Load field mappings from EntityMapper
        normalizer.load_field_mappings(entity_mapper.get_field_choices)
        
        # Normalize ticket
        normalized = normalizer.normalize_ticket(ticket, conversations)
    """
    
    def __init__(self) -> None:
        self._cache = NormalizerCache()
        self._field_mappings = FieldMappings()
    
    # ========================================================================
    # Cache Loading
    # ========================================================================
    
    def load_contacts(self, contacts: list[dict[str, Any]]) -> None:
        """연락처 캐시 로드"""
        for contact in contacts:
            if contact.get("id"):
                name = contact.get("name") or contact.get("email") or ""
                self._cache.contacts[contact["id"]] = name
        logger.debug(f"Loaded {len(contacts)} contacts into cache")
    
    def load_agents(self, agents: list[dict[str, Any]]) -> None:
        """에이전트 캐시 로드"""
        for agent in agents:
            if agent.get("id"):
                name = ""
                if "contact" in agent and agent["contact"]:
                    name = agent["contact"].get("name", "")
                if not name:
                    name = agent.get("name") or agent.get("email") or ""
                self._cache.agents[agent["id"]] = name
        logger.debug(f"Loaded {len(agents)} agents into cache")
    
    def load_groups(self, groups: list[dict[str, Any]]) -> None:
        """그룹 캐시 로드"""
        for group in groups:
            if group.get("id"):
                self._cache.groups[group["id"]] = group.get("name", "")
        logger.debug(f"Loaded {len(groups)} groups into cache")
    
    def load_products(self, products: list[dict[str, Any]]) -> None:
        """제품 캐시 로드"""
        for product in products:
            if product.get("id"):
                self._cache.products[product["id"]] = product.get("name", "")
        logger.debug(f"Loaded {len(products)} products into cache")
    
    def load_categories(self, categories: list[dict[str, Any]]) -> None:
        """카테고리 캐시 로드"""
        for category in categories:
            if category.get("id"):
                self._cache.categories[category["id"]] = category.get("name", "")
        logger.debug(f"Loaded {len(categories)} categories into cache")
    
    def load_folders(self, folders: list[dict[str, Any]]) -> None:
        """폴더 캐시 로드"""
        for folder in folders:
            if folder.get("id"):
                self._cache.folders[folder["id"]] = folder.get("name", "")
        logger.debug(f"Loaded {len(folders)} folders into cache")
    
    def load_field_mappings(self, mappings: FieldMappings) -> None:
        """필드 매핑 로드 (EntityMapper에서)"""
        self._field_mappings = mappings
        logger.debug("Field mappings updated")
    
    def load_field_mappings_from_entity_mapper(
        self,
        status: dict[int, str] | None = None,
        priority: dict[int, str] | None = None,
        source: dict[int, str] | None = None,
        type_choices: dict[int, str] | None = None,
    ) -> None:
        """EntityMapper의 get_field_choices에서 필드 매핑 로드"""
        if status:
            self._field_mappings.status = status
        if priority:
            self._field_mappings.priority = priority
        if source:
            self._field_mappings.source = source
        if type_choices:
            self._field_mappings.type = type_choices
        logger.debug("Field mappings loaded from EntityMapper")
    
    # ========================================================================
    # Status/Priority/Source Normalization
    # ========================================================================
    
    def _normalize_ticket_status(self, status: int) -> str:
        """티켓 상태 정규화 (숫자 → 문자열)"""
        # EntityMapper 매핑 우선
        if status in self._field_mappings.status:
            return self._field_mappings.status[status]
        
        # 기본 매핑
        status_map: dict[int, str] = {
            TicketStatus.OPEN.value: "Open",
            TicketStatus.PENDING.value: "Pending",
            TicketStatus.RESOLVED.value: "Resolved",
            TicketStatus.CLOSED.value: "Closed",
        }
        return status_map.get(status, str(status))
    
    def _normalize_ticket_priority(self, priority: int) -> str:
        """티켓 우선순위 정규화 (숫자 → 문자열)"""
        if priority in self._field_mappings.priority:
            return self._field_mappings.priority[priority]
        
        priority_map: dict[int, str] = {
            TicketPriority.LOW.value: "Low",
            TicketPriority.MEDIUM.value: "Medium",
            TicketPriority.HIGH.value: "High",
            TicketPriority.URGENT.value: "Urgent",
        }
        return priority_map.get(priority, str(priority))
    
    def _normalize_ticket_source(self, source: int) -> str:
        """티켓 소스 정규화 (숫자 → 문자열)"""
        if source in self._field_mappings.source:
            return self._field_mappings.source[source]
        
        source_map: dict[int, str] = {
            TicketSource.EMAIL.value: "Email",
            TicketSource.PORTAL.value: "Portal",
            TicketSource.PHONE.value: "Phone",
            TicketSource.CHAT.value: "Chat",
            TicketSource.FEEDBACK.value: "Feedback",
            TicketSource.OUTBOUND.value: "Outbound",
        }
        return source_map.get(source, str(source))
    
    def _normalize_article_status(self, status: int) -> str:
        """아티클 상태 정규화 (숫자 → 문자열)"""
        status_map: dict[int, str] = {
            ArticleStatus.DRAFT.value: "Draft",
            ArticleStatus.PUBLISHED.value: "Published",
        }
        return status_map.get(status, str(status))
    
    def _normalize_custom_fields(
        self, 
        fields: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """커스텀 필드 정규화"""
        if not fields:
            return None
        
        normalized: dict[str, Any] = {}
        
        for key, value in fields.items():
            mapping = self._field_mappings.custom_fields.get(key)
            if mapping and value is not None:
                mapped_value = mapping.get(str(value))
                normalized[key] = mapped_value if mapped_value is not None else value
            else:
                normalized[key] = value
        
        return normalized
    
    # ========================================================================
    # Ticket Normalization
    # ========================================================================
    
    def normalize_ticket(
        self,
        ticket: dict[str, Any],
        conversations: list[dict[str, Any]] | None = None,
    ) -> NormalizedTicket:
        """
        티켓 정규화
        
        Supports EntityMapper labels (responder_label, group_label, etc.)
        passed through enriched ticket dict.
        
        Args:
            ticket: Raw Freshdesk ticket (may include EntityMapper labels)
            conversations: Optional conversation list to include
        
        Returns:
            NormalizedTicket with human-readable labels
        """
        # Type label
        ticket_type = ticket.get("type")
        if ticket_type and self._field_mappings.type:
            type_label = self._field_mappings.type.get(ticket_type, ticket_type)
        else:
            type_label = ticket_type
        
        # Requester label (EntityMapper label → cache → fallback)
        requester_id = ticket.get("requester_id")
        requester_label = (
            ticket.get("requester_label")  # EntityMapper enriched
            or self._cache.contacts.get(requester_id, "")
            or f"Contact_{requester_id}" if requester_id else ""
        )
        
        # Responder label
        responder_id = ticket.get("responder_id")
        responder_label = None
        if responder_id:
            responder_label = (
                ticket.get("responder_label")
                or self._cache.agents.get(responder_id, "")
                or f"Agent_{responder_id}"
            )
        
        # Group label
        group_id = ticket.get("group_id")
        group_label = None
        if group_id:
            group_label = (
                ticket.get("group_label")
                or self._cache.groups.get(group_id, "")
                or f"Group_{group_id}"
            )
        
        # Product label
        product_id = ticket.get("product_id")
        product_label = None
        if product_id:
            product_label = (
                ticket.get("product_label")
                or self._cache.products.get(product_id, "")
                or f"Product_{product_id}"
            )
        
        # Normalize conversations
        normalized_conversations = None
        if conversations:
            normalized_conversations = [
                self.normalize_conversation(conv)
                for conv in conversations
            ]
        
        return NormalizedTicket(
            id=ticket["id"],
            subject=ticket.get("subject", ""),
            description_text=ticket.get("description_text", ""),
            status=self._normalize_ticket_status(ticket.get("status", 0)),
            priority=self._normalize_ticket_priority(ticket.get("priority", 0)),
            source=self._normalize_ticket_source(ticket.get("source", 0)),
            type=type_label,
            requester=requester_label,
            requester_id=requester_id or 0,
            responder=responder_label,
            responder_id=responder_id,
            group=group_label,
            group_id=group_id,
            product=product_label,
            product_id=product_id,
            tags=ticket.get("tags") or [],
            created_at=ticket.get("created_at", ""),
            updated_at=ticket.get("updated_at", ""),
            due_by=ticket.get("due_by"),
            fr_due_by=ticket.get("fr_due_by"),
            custom_fields=self._normalize_custom_fields(ticket.get("custom_fields")),
            conversations=normalized_conversations,
        )
    
    def normalize_tickets(
        self,
        tickets: list[dict[str, Any]],
    ) -> list[NormalizedTicket]:
        """여러 티켓 정규화"""
        logger.info(f"Normalizing {len(tickets)} tickets")
        return [self.normalize_ticket(ticket) for ticket in tickets]
    
    # ========================================================================
    # Conversation Normalization
    # ========================================================================
    
    def normalize_conversation(
        self,
        conversation: dict[str, Any],
    ) -> NormalizedConversation:
        """
        대화 정규화
        
        Uses body_text (already cleaned, no HTML)
        """
        user_id = conversation.get("user_id")
        user_name = (
            self._cache.contacts.get(user_id, "")
            if user_id else ""
        ) or conversation.get("from_email") or f"User_{user_id}" if user_id else ""
        
        return NormalizedConversation(
            id=conversation["id"],
            body_text=conversation.get("body_text", ""),
            from_email=conversation.get("from_email"),
            to_emails=conversation.get("to_emails"),
            user_name=user_name,
            incoming=conversation.get("incoming", False),
            private=conversation.get("private", False),
            created_at=conversation.get("created_at", ""),
            updated_at=conversation.get("updated_at", ""),
            attachments=conversation.get("attachments"),
        )
    
    def normalize_conversations(
        self,
        conversations: list[dict[str, Any]],
    ) -> list[NormalizedConversation]:
        """여러 대화 정규화"""
        logger.info(f"Normalizing {len(conversations)} conversations")
        return [self.normalize_conversation(conv) for conv in conversations]
    
    # ========================================================================
    # Article Normalization
    # ========================================================================
    
    def normalize_article(
        self,
        article: dict[str, Any],
    ) -> NormalizedArticle:
        """
        아티클 정규화
        
        Supports EntityMapper labels (category_label, folder_label)
        """
        category_id = article.get("category_id", 0)
        folder_id = article.get("folder_id", 0)
        
        # Category label (EntityMapper → cache → fallback)
        category_label = (
            article.get("category_label")
            or self._cache.categories.get(category_id, "")
            or f"Category_{category_id}"
        )
        
        # Folder label
        folder_label = (
            article.get("folder_label")
            or self._cache.folders.get(folder_id, "")
            or f"Folder_{folder_id}"
        )
        
        return NormalizedArticle(
            id=article["id"],
            title=article.get("title", ""),
            description_text=article.get("description_text", ""),
            status=self._normalize_article_status(article.get("status", 0)),
            category=category_label,
            category_id=category_id,
            folder=folder_label,
            folder_id=folder_id,
            tags=article.get("tags") or [],
            seo_data=article.get("seo_data"),
            created_at=article.get("created_at", ""),
            updated_at=article.get("updated_at", ""),
        )
    
    def normalize_articles(
        self,
        articles: list[dict[str, Any]],
    ) -> list[NormalizedArticle]:
        """여러 아티클 정규화"""
        logger.info(f"Normalizing {len(articles)} articles")
        return [self.normalize_article(article) for article in articles]
    
    # ========================================================================
    # Cache Management
    # ========================================================================
    
    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._cache = NormalizerCache()
        logger.debug("Cache cleared")


def create_normalizer() -> FreshdeskNormalizer:
    """Factory function to create normalizer"""
    return FreshdeskNormalizer()
