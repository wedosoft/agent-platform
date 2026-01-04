"""콘텐츠 저장소 - 시나리오, 지식 문서, 대화 히스토리 통합 관리."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from supabase import Client

LOGGER = logging.getLogger(__name__)

TABLE_SCENARIO_CATEGORIES = "scenario_categories"
TABLE_SCENARIOS = "scenarios"
TABLE_SCENARIO_CHOICES = "scenario_choices"
TABLE_CHAT_HISTORY = "chat_history"
TABLE_CHAT_SUMMARIES = "chat_summaries"


class ScenarioCategory(BaseModel):
    """시나리오 카테고리 모델."""
    id: str
    name: str
    name_ko: str
    icon: Optional[str] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class ScenarioChoice(BaseModel):
    """시나리오 선택지 모델."""
    id: str
    scenario_id: str
    text: str
    text_ko: str
    display_order: int = 0
    is_recommended: bool = False


class Scenario(BaseModel):
    """시나리오 모델."""
    id: str
    category_id: str
    title: str
    title_ko: str
    icon: Optional[str] = None
    description: str
    description_ko: str
    display_order: int = 0
    is_active: bool = True
    choices: List[ScenarioChoice] = []


class ChatMessage(BaseModel):
    """대화 메시지 모델."""
    id: Optional[str] = None
    session_id: str
    context_type: str = "mentor"
    context_id: Optional[str] = None
    role: str
    content: str
    turn_number: int = 0
    created_at: Optional[str] = None


class ChatSummary(BaseModel):
    """대화 요약 모델."""
    id: Optional[str] = None
    session_id: str
    context_type: str = "mentor"
    context_id: Optional[str] = None
    summary: str
    summarized_turns: int = 0
    last_turn_number: int = 0


class ContentRepositoryError(RuntimeError):
    """콘텐츠 저장소 에러."""
    pass


class ContentRepository:
    """콘텐츠 저장소 (시나리오, 대화 히스토리 통합 관리)."""

    def __init__(self, client: Client) -> None:
        self.client = client

    # ============================================
    # 시나리오 카테고리 관리
    # ============================================

    async def get_categories(self, active_only: bool = True) -> List[ScenarioCategory]:
        """시나리오 카테고리 목록 조회."""
        try:
            query = self.client.table(TABLE_SCENARIO_CATEGORIES).select("*")
            if active_only:
                query = query.eq("is_active", True)
            response = query.order("display_order").execute()
            
            return [
                ScenarioCategory(
                    id=row["id"],
                    name=row["name"],
                    name_ko=row["name_ko"],
                    icon=row.get("icon"),
                    description=row.get("description"),
                    description_ko=row.get("description_ko"),
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                )
                for row in (response.data or [])
            ]
        except Exception as e:
            LOGGER.error(f"Failed to get scenario categories: {e}")
            return []

    async def create_category(
        self,
        id: str,
        name: str,
        name_ko: str,
        icon: Optional[str] = None,
        description: Optional[str] = None,
        description_ko: Optional[str] = None,
        display_order: int = 0,
    ) -> ScenarioCategory:
        """시나리오 카테고리 생성."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": id,
            "name": name,
            "name_ko": name_ko,
            "icon": icon,
            "description": description,
            "description_ko": description_ko,
            "display_order": display_order,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            response = self.client.table(TABLE_SCENARIO_CATEGORIES).insert(data).execute()
            if response.data:
                row = response.data[0]
                return ScenarioCategory(
                    id=row["id"],
                    name=row["name"],
                    name_ko=row["name_ko"],
                    icon=row.get("icon"),
                    description=row.get("description"),
                    description_ko=row.get("description_ko"),
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                )
            raise ContentRepositoryError("Failed to create category")
        except Exception as e:
            LOGGER.error(f"Failed to create scenario category: {e}")
            raise ContentRepositoryError(str(e)) from e

    async def update_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        name_ko: Optional[str] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
        description_ko: Optional[str] = None,
        display_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ScenarioCategory]:
        """시나리오 카테고리 수정."""
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if name_ko is not None:
            data["name_ko"] = name_ko
        if icon is not None:
            data["icon"] = icon
        if description is not None:
            data["description"] = description
        if description_ko is not None:
            data["description_ko"] = description_ko
        if display_order is not None:
            data["display_order"] = display_order
        if is_active is not None:
            data["is_active"] = is_active

        if not data:
            return await self.get_category(category_id)

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            response = (
                self.client.table(TABLE_SCENARIO_CATEGORIES)
                .update(data)
                .eq("id", category_id)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return ScenarioCategory(
                    id=row["id"],
                    name=row["name"],
                    name_ko=row["name_ko"],
                    icon=row.get("icon"),
                    description=row.get("description"),
                    description_ko=row.get("description_ko"),
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to update scenario category: {e}")
            return None

    async def get_category(self, category_id: str) -> Optional[ScenarioCategory]:
        """시나리오 카테고리 단건 조회."""
        try:
            response = (
                self.client.table(TABLE_SCENARIO_CATEGORIES)
                .select("*")
                .eq("id", category_id)
                .limit(1)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return ScenarioCategory(
                    id=row["id"],
                    name=row["name"],
                    name_ko=row["name_ko"],
                    icon=row.get("icon"),
                    description=row.get("description"),
                    description_ko=row.get("description_ko"),
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get scenario category: {e}")
            return None

    # ============================================
    # 시나리오 관리
    # ============================================

    async def get_scenarios(
        self,
        category_id: Optional[str] = None,
        active_only: bool = True,
        include_choices: bool = True,
    ) -> List[Scenario]:
        """시나리오 목록 조회."""
        try:
            query = self.client.table(TABLE_SCENARIOS).select("*")
            if category_id:
                query = query.eq("category_id", category_id)
            if active_only:
                query = query.eq("is_active", True)
            response = query.order("display_order").execute()

            scenarios = []
            for row in (response.data or []):
                choices = []
                if include_choices:
                    choices = await self.get_scenario_choices(row["id"])
                
                scenarios.append(Scenario(
                    id=row["id"],
                    category_id=row["category_id"],
                    title=row["title"],
                    title_ko=row["title_ko"],
                    icon=row.get("icon"),
                    description=row["description"],
                    description_ko=row["description_ko"],
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                    choices=choices,
                ))
            return scenarios
        except Exception as e:
            LOGGER.error(f"Failed to get scenarios: {e}")
            return []

    async def get_scenario(
        self, scenario_id: str, include_choices: bool = True
    ) -> Optional[Scenario]:
        """시나리오 단건 조회."""
        try:
            response = (
                self.client.table(TABLE_SCENARIOS)
                .select("*")
                .eq("id", scenario_id)
                .limit(1)
                .execute()
            )
            if response.data:
                row = response.data[0]
                choices = []
                if include_choices:
                    choices = await self.get_scenario_choices(scenario_id)
                
                return Scenario(
                    id=row["id"],
                    category_id=row["category_id"],
                    title=row["title"],
                    title_ko=row["title_ko"],
                    icon=row.get("icon"),
                    description=row["description"],
                    description_ko=row["description_ko"],
                    display_order=row.get("display_order", 0),
                    is_active=row.get("is_active", True),
                    choices=choices,
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get scenario: {e}")
            return None

    async def create_scenario(
        self,
        id: str,
        category_id: str,
        title: str,
        title_ko: str,
        description: str,
        description_ko: str,
        icon: Optional[str] = None,
        display_order: int = 0,
        choices: Optional[List[Dict[str, Any]]] = None,
    ) -> Scenario:
        """시나리오 생성."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": id,
            "category_id": category_id,
            "title": title,
            "title_ko": title_ko,
            "icon": icon,
            "description": description,
            "description_ko": description_ko,
            "display_order": display_order,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            response = self.client.table(TABLE_SCENARIOS).insert(data).execute()
            if not response.data:
                raise ContentRepositoryError("Failed to create scenario")
            
            row = response.data[0]
            
            created_choices = []
            if choices:
                for choice_data in choices:
                    choice = await self.create_scenario_choice(
                        id=choice_data["id"],
                        scenario_id=id,
                        text=choice_data["text"],
                        text_ko=choice_data["text_ko"],
                        display_order=choice_data.get("display_order", 0),
                        is_recommended=choice_data.get("is_recommended", False),
                    )
                    created_choices.append(choice)
            
            return Scenario(
                id=row["id"],
                category_id=row["category_id"],
                title=row["title"],
                title_ko=row["title_ko"],
                icon=row.get("icon"),
                description=row["description"],
                description_ko=row["description_ko"],
                display_order=row.get("display_order", 0),
                is_active=row.get("is_active", True),
                choices=created_choices,
            )
        except Exception as e:
            LOGGER.error(f"Failed to create scenario: {e}")
            raise ContentRepositoryError(str(e)) from e

    async def update_scenario(
        self,
        scenario_id: str,
        category_id: Optional[str] = None,
        title: Optional[str] = None,
        title_ko: Optional[str] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
        description_ko: Optional[str] = None,
        display_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Scenario]:
        """시나리오 수정."""
        data: Dict[str, Any] = {}
        if category_id is not None:
            data["category_id"] = category_id
        if title is not None:
            data["title"] = title
        if title_ko is not None:
            data["title_ko"] = title_ko
        if icon is not None:
            data["icon"] = icon
        if description is not None:
            data["description"] = description
        if description_ko is not None:
            data["description_ko"] = description_ko
        if display_order is not None:
            data["display_order"] = display_order
        if is_active is not None:
            data["is_active"] = is_active

        if not data:
            return await self.get_scenario(scenario_id)

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            response = (
                self.client.table(TABLE_SCENARIOS)
                .update(data)
                .eq("id", scenario_id)
                .execute()
            )
            if response.data:
                return await self.get_scenario(scenario_id)
            return None
        except Exception as e:
            LOGGER.error(f"Failed to update scenario: {e}")
            return None

    async def delete_scenario(self, scenario_id: str) -> bool:
        """시나리오 삭제 (선택지도 함께 삭제됨 - CASCADE)."""
        try:
            self.client.table(TABLE_SCENARIOS).delete().eq("id", scenario_id).execute()
            return True
        except Exception as e:
            LOGGER.error(f"Failed to delete scenario: {e}")
            return False

    # ============================================
    # 시나리오 선택지 관리
    # ============================================

    async def get_scenario_choices(self, scenario_id: str) -> List[ScenarioChoice]:
        """시나리오 선택지 목록 조회."""
        try:
            response = (
                self.client.table(TABLE_SCENARIO_CHOICES)
                .select("*")
                .eq("scenario_id", scenario_id)
                .order("display_order")
                .execute()
            )
            return [
                ScenarioChoice(
                    id=row["id"],
                    scenario_id=row["scenario_id"],
                    text=row["text"],
                    text_ko=row["text_ko"],
                    display_order=row.get("display_order", 0),
                    is_recommended=row.get("is_recommended", False),
                )
                for row in (response.data or [])
            ]
        except Exception as e:
            LOGGER.error(f"Failed to get scenario choices: {e}")
            return []

    async def create_scenario_choice(
        self,
        id: str,
        scenario_id: str,
        text: str,
        text_ko: str,
        display_order: int = 0,
        is_recommended: bool = False,
    ) -> ScenarioChoice:
        """시나리오 선택지 생성."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": id,
            "scenario_id": scenario_id,
            "text": text,
            "text_ko": text_ko,
            "display_order": display_order,
            "is_recommended": is_recommended,
            "created_at": now,
            "updated_at": now,
        }

        try:
            response = self.client.table(TABLE_SCENARIO_CHOICES).insert(data).execute()
            if response.data:
                row = response.data[0]
                return ScenarioChoice(
                    id=row["id"],
                    scenario_id=row["scenario_id"],
                    text=row["text"],
                    text_ko=row["text_ko"],
                    display_order=row.get("display_order", 0),
                    is_recommended=row.get("is_recommended", False),
                )
            raise ContentRepositoryError("Failed to create scenario choice")
        except Exception as e:
            LOGGER.error(f"Failed to create scenario choice: {e}")
            raise ContentRepositoryError(str(e)) from e

    async def update_scenario_choice(
        self,
        choice_id: str,
        text: Optional[str] = None,
        text_ko: Optional[str] = None,
        display_order: Optional[int] = None,
        is_recommended: Optional[bool] = None,
    ) -> Optional[ScenarioChoice]:
        """시나리오 선택지 수정."""
        data: Dict[str, Any] = {}
        if text is not None:
            data["text"] = text
        if text_ko is not None:
            data["text_ko"] = text_ko
        if display_order is not None:
            data["display_order"] = display_order
        if is_recommended is not None:
            data["is_recommended"] = is_recommended

        if not data:
            return None

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            response = (
                self.client.table(TABLE_SCENARIO_CHOICES)
                .update(data)
                .eq("id", choice_id)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return ScenarioChoice(
                    id=row["id"],
                    scenario_id=row["scenario_id"],
                    text=row["text"],
                    text_ko=row["text_ko"],
                    display_order=row.get("display_order", 0),
                    is_recommended=row.get("is_recommended", False),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to update scenario choice: {e}")
            return None

    async def delete_scenario_choice(self, choice_id: str) -> bool:
        """시나리오 선택지 삭제."""
        try:
            self.client.table(TABLE_SCENARIO_CHOICES).delete().eq("id", choice_id).execute()
            return True
        except Exception as e:
            LOGGER.error(f"Failed to delete scenario choice: {e}")
            return False

    # ============================================
    # 대화 히스토리 관리
    # ============================================

    async def get_chat_history(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[ChatMessage]:
        """대화 히스토리 조회."""
        try:
            query = (
                self.client.table(TABLE_CHAT_HISTORY)
                .select("*")
                .eq("session_id", session_id)
                .eq("context_type", context_type)
            )
            
            if context_id:
                query = query.eq("context_id", context_id)
            else:
                query = query.is_("context_id", "null")
            
            response = (
                query.order("turn_number", desc=False)
                .limit(limit)
                .execute()
            )
            
            return [
                ChatMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    context_type=row["context_type"],
                    context_id=row.get("context_id"),
                    role=row["role"],
                    content=row["content"],
                    turn_number=row["turn_number"],
                    created_at=row.get("created_at"),
                )
                for row in (response.data or [])
            ]
        except Exception as e:
            LOGGER.error(f"Failed to get chat history: {e}")
            return []

    async def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> ChatMessage:
        """대화 메시지 추가."""
        try:
            existing = await self.get_chat_history(
                session_id, context_type, context_id, limit=100
            )
            turn_number = len(existing)
            
            now = datetime.now(timezone.utc).isoformat()
            data = {
                "session_id": session_id,
                "context_type": context_type,
                "context_id": context_id,
                "role": role,
                "content": content,
                "turn_number": turn_number,
                "created_at": now,
            }

            response = self.client.table(TABLE_CHAT_HISTORY).insert(data).execute()
            if response.data:
                row = response.data[0]
                return ChatMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    context_type=row["context_type"],
                    context_id=row.get("context_id"),
                    role=row["role"],
                    content=row["content"],
                    turn_number=row["turn_number"],
                    created_at=row.get("created_at"),
                )
            raise ContentRepositoryError("Failed to add chat message")
        except Exception as e:
            LOGGER.error(f"Failed to add chat message: {e}")
            raise ContentRepositoryError(str(e)) from e

    async def clear_chat_history(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> bool:
        """대화 히스토리 삭제."""
        try:
            query = (
                self.client.table(TABLE_CHAT_HISTORY)
                .delete()
                .eq("session_id", session_id)
                .eq("context_type", context_type)
            )
            
            if context_id:
                query = query.eq("context_id", context_id)
            else:
                query = query.is_("context_id", "null")
            
            query.execute()
            return True
        except Exception as e:
            LOGGER.error(f"Failed to clear chat history: {e}")
            return False

    async def get_chat_summary(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> Optional[ChatSummary]:
        """대화 요약 조회."""
        try:
            query = (
                self.client.table(TABLE_CHAT_SUMMARIES)
                .select("*")
                .eq("session_id", session_id)
                .eq("context_type", context_type)
            )
            
            if context_id:
                query = query.eq("context_id", context_id)
            else:
                query = query.is_("context_id", "null")
            
            response = query.limit(1).execute()
            
            if response.data:
                row = response.data[0]
                return ChatSummary(
                    id=row["id"],
                    session_id=row["session_id"],
                    context_type=row["context_type"],
                    context_id=row.get("context_id"),
                    summary=row["summary"],
                    summarized_turns=row["summarized_turns"],
                    last_turn_number=row["last_turn_number"],
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get chat summary: {e}")
            return None

    async def save_chat_summary(
        self,
        session_id: str,
        summary: str,
        summarized_turns: int,
        last_turn_number: int,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> ChatSummary:
        """대화 요약 저장 (upsert)."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "context_type": context_type,
            "context_id": context_id,
            "summary": summary,
            "summarized_turns": summarized_turns,
            "last_turn_number": last_turn_number,
            "updated_at": now,
        }

        try:
            existing = await self.get_chat_summary(session_id, context_type, context_id)
            
            if existing:
                response = (
                    self.client.table(TABLE_CHAT_SUMMARIES)
                    .update(data)
                    .eq("id", existing.id)
                    .execute()
                )
            else:
                data["created_at"] = now
                response = self.client.table(TABLE_CHAT_SUMMARIES).insert(data).execute()
            
            if response.data:
                row = response.data[0]
                return ChatSummary(
                    id=row["id"],
                    session_id=row["session_id"],
                    context_type=row["context_type"],
                    context_id=row.get("context_id"),
                    summary=row["summary"],
                    summarized_turns=row["summarized_turns"],
                    last_turn_number=row["last_turn_number"],
                )
            raise ContentRepositoryError("Failed to save chat summary")
        except Exception as e:
            LOGGER.error(f"Failed to save chat summary: {e}")
            raise ContentRepositoryError(str(e)) from e


def get_content_repository(client: Client) -> ContentRepository:
    """ContentRepository 인스턴스 생성."""
    return ContentRepository(client)
