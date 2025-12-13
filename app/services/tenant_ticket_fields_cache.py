"""테넌트별 Ticket Fields 스키마 캐시 (Supabase).

목표
- Freshdesk의 /ticket_fields 호출은 상대적으로 느리고(또는 rate-limit 영향)
  매 모달 오픈마다 호출되면 UX가 나빠짐
- tenants/tenant_platforms(공통 Supabase) 기준으로 tenant를 식별하고,
  ticket_fields 스키마(JSON)를 Supabase에 저장/재사용

설계
- 캐시 Key: (tenant_id(UUID), platform)
- 저장: Supabase table `tenant_ticket_fields`
- 조회: TTL(기본 24h) 안이면 Supabase 캐시 반환, 아니면 Freshdesk에서 재수집 후 upsert

주의
- Supabase Python client는 동기 I/O라서, 고QPS 환경에서는 별도 async 래퍼/스레드풀 고려 가능.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.core.config import get_settings
from app.services.freshdesk_client import FreshdeskClient

logger = logging.getLogger(__name__)


def _normalize_domain(domain: str) -> str:
    d = (domain or "").strip()
    d = d.replace("https://", "").replace("http://", "").rstrip("/")
    return d


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
        raise ValueError("Supabase credentials not configured (SUPABASE_COMMON_*)")
    return create_client(settings.supabase_common_url, settings.supabase_common_service_role_key)


@dataclass
class TicketFieldsCacheResult:
    ticket_fields: List[Dict[str, Any]]
    source: str  # 'supabase' | 'freshdesk'
    tenant_uuid: Optional[str] = None
    schema_hash: Optional[str] = None
    updated_at: Optional[str] = None


class TenantTicketFieldsCache:
    def __init__(self, *, ttl: timedelta = timedelta(hours=24)) -> None:
        self._ttl = ttl
        try:
            self._sb: Optional[Client] = _get_supabase_client()
        except ValueError:
            # Supabase 미설정 환경에서도 동작해야 하므로 캐시를 비활성화하고 Freshdesk 직조회로 폴백.
            self._sb = None

    def _compute_hash(self, ticket_fields: List[Dict[str, Any]]) -> str:
        blob = json.dumps(ticket_fields, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _parse_updated_at(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _is_fresh(self, updated_at: Optional[datetime]) -> bool:
        if not updated_at:
            return False
        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return (now - updated_at) <= self._ttl

    def resolve_tenant_uuid(
        self,
        *,
        tenant_slug: str,
        platform: str,
        domain: Optional[str],
    ) -> Optional[str]:
        """Supabase `tenants.id`(UUID) 를 반환.

        우선순위:
        1) domain 기반 RPC(get_tenant_by_domain)로 tenant_id 조회
        2) tenant_slug로 tenants 테이블 직접 조회
        """
        normalized_domain = _normalize_domain(domain or "")

        if self._sb is None:
            return None

        if normalized_domain:
            try:
                resp = self._sb.rpc("get_tenant_by_domain", {"p_domain": normalized_domain}).execute()
                rows = resp.data or []
                for row in rows:
                    if (row.get("platform") or "").lower() == platform.lower() and row.get("enabled") is True:
                        return str(row.get("tenant_id"))
            except Exception as e:
                logger.warning("Supabase RPC get_tenant_by_domain failed: %s", e)

        if tenant_slug:
            try:
                resp = (
                    self._sb.table("tenants")
                    .select("id")
                    .eq("slug", tenant_slug)
                    .is_("deleted_at", "null")
                    .single()
                    .execute()
                )
                if resp.data and resp.data.get("id"):
                    return str(resp.data["id"])
            except Exception as e:
                logger.warning("Supabase tenants.slug lookup failed: %s", e)

        return None

    def get_cached_ticket_fields(self, *, tenant_uuid: str, platform: str) -> Optional[TicketFieldsCacheResult]:
        if self._sb is None:
            return None
        try:
            resp = (
                self._sb.table("tenant_ticket_fields")
                .select("ticket_fields, schema_hash, updated_at")
                .eq("tenant_id", tenant_uuid)
                .eq("platform", platform)
                .single()
                .execute()
            )
            data = resp.data
            if not data:
                return None

            updated_at_dt = self._parse_updated_at(data.get("updated_at"))
            if not self._is_fresh(updated_at_dt):
                return None

            fields = data.get("ticket_fields")
            if not isinstance(fields, list):
                return None

            return TicketFieldsCacheResult(
                ticket_fields=fields,
                source="supabase",
                tenant_uuid=tenant_uuid,
                schema_hash=data.get("schema_hash"),
                updated_at=data.get("updated_at"),
            )
        except Exception:
            return None

    def upsert_ticket_fields(
        self,
        *,
        tenant_uuid: str,
        platform: str,
        domain: str,
        ticket_fields: List[Dict[str, Any]],
    ) -> TicketFieldsCacheResult:
        schema_hash = self._compute_hash(ticket_fields)

        if self._sb is None:
            return TicketFieldsCacheResult(
                ticket_fields=ticket_fields,
                source="freshdesk",
                tenant_uuid=tenant_uuid,
                schema_hash=schema_hash,
            )

        payload = {
            "tenant_id": tenant_uuid,
            "platform": platform,
            "ticket_fields": ticket_fields,
            "schema_hash": schema_hash,
            "fetched_from_domain": _normalize_domain(domain),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._sb.table("tenant_ticket_fields").upsert(payload).execute()
        except Exception as e:
            logger.warning("Supabase upsert tenant_ticket_fields failed: %s", e)

        return TicketFieldsCacheResult(
            ticket_fields=ticket_fields,
            source="freshdesk",
            tenant_uuid=tenant_uuid,
            schema_hash=schema_hash,
        )

    async def get_or_refresh_freshdesk_ticket_fields(
        self,
        *,
        tenant_slug: str,
        freshdesk_domain: str,
        freshdesk_api_key: str,
        platform: str = "freshdesk",
        force_refresh: bool = False,
    ) -> TicketFieldsCacheResult:
        normalized_domain = _normalize_domain(freshdesk_domain)

        tenant_uuid = self.resolve_tenant_uuid(
            tenant_slug=tenant_slug,
            platform=platform,
            domain=normalized_domain,
        )

        if tenant_uuid and not force_refresh:
            cached = self.get_cached_ticket_fields(tenant_uuid=tenant_uuid, platform=platform)
            if cached:
                return cached

        client = FreshdeskClient(domain=normalized_domain, api_key=freshdesk_api_key)
        try:
            fields = await client.get_ticket_fields()
        finally:
            await client.close()

        if not tenant_uuid:
            return TicketFieldsCacheResult(ticket_fields=fields, source="freshdesk")

        return self.upsert_ticket_fields(
            tenant_uuid=tenant_uuid,
            platform=platform,
            domain=normalized_domain,
            ticket_fields=fields,
        )


@lru_cache(maxsize=1)
def get_tenant_ticket_fields_cache() -> TenantTicketFieldsCache:
    return TenantTicketFieldsCache()