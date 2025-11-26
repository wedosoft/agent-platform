"""
FDK Authentication Middleware

Freshdesk FDK Custom App에서 전달하는 헤더를 통한 인증 처리
X-Freshdesk-Domain, X-Freshdesk-API-Key 헤더 기반

FDK serverless 함수에서 secure iparams를 통해 자격 증명을 가져와
백엔드 API 호출 시 헤더로 전달하는 방식
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass
class FDKContext:
    """FDK Custom App 인증 컨텍스트"""

    domain: str  # Freshdesk 도메인 (예: company.freshdesk.com)
    api_key: str  # Freshdesk API 키
    tenant_id: str  # 테넌트 ID (도메인에서 추출)
    verified: bool = False  # API 키 검증 여부
    agent_email: Optional[str] = None  # 현재 상담원 이메일
    agent_id: Optional[int] = None  # 현재 상담원 ID


async def verify_freshdesk_credentials(domain: str, api_key: str) -> tuple[bool, Optional[dict]]:
    """
    Freshdesk API 키 검증

    Args:
        domain: Freshdesk 도메인
        api_key: Freshdesk API 키

    Returns:
        (검증 성공 여부, 에이전트 정보)
    """
    if not domain or not api_key:
        return False, None

    # 도메인 정규화
    normalized_domain = domain
    if not normalized_domain.endswith(".freshdesk.com"):
        normalized_domain = f"{normalized_domain}.freshdesk.com"

    url = f"https://{normalized_domain}/api/v2/agents/me"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                auth=(api_key, "X"),  # Freshdesk uses API key as username
            )
            if response.status_code == 200:
                agent_info = response.json()
                return True, agent_info
            else:
                logger.warning(f"Freshdesk API 검증 실패: status={response.status_code}")
                return False, None
    except httpx.RequestError as e:
        logger.error(f"Freshdesk API 연결 오류: {e}")
        return False, None


def extract_tenant_from_domain(domain: str) -> str:
    """
    도메인에서 테넌트 ID 추출

    예: company.freshdesk.com -> company
    """
    if not domain:
        return ""

    # 프로토콜 제거
    domain = domain.replace("https://", "").replace("http://", "")

    # 서브도메인 추출
    parts = domain.split(".")
    if len(parts) >= 1:
        return parts[0].lower()

    return domain.lower()


async def get_fdk_context(request: Request) -> FDKContext:
    """
    FDK Custom App 인증 컨텍스트 추출

    FastAPI 의존성으로 사용

    Required headers:
    - X-Freshdesk-Domain: Freshdesk 도메인
    - X-Freshdesk-API-Key: Freshdesk API 키

    Optional headers:
    - X-Tenant-ID: 테넌트 ID (없으면 도메인에서 추출)

    Returns:
        FDKContext

    Raises:
        HTTPException: 인증 실패 시
    """
    domain = request.headers.get("X-Freshdesk-Domain", "").strip()
    api_key = request.headers.get("X-Freshdesk-API-Key", "").strip()
    tenant_id = request.headers.get("X-Tenant-ID", "").strip()

    # 헤더 검증
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Freshdesk-Domain 헤더가 필요합니다",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Freshdesk-API-Key 헤더가 필요합니다",
        )

    # 테넌트 ID 추출
    if not tenant_id:
        tenant_id = extract_tenant_from_domain(domain)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="테넌트 ID를 결정할 수 없습니다",
        )

    # API 키 검증
    verified, agent_info = await verify_freshdesk_credentials(domain, api_key)

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="유효하지 않은 Freshdesk 자격 증명입니다",
        )

    # 에이전트 정보 추출
    agent_email = None
    agent_id = None
    if agent_info:
        contact = agent_info.get("contact", {})
        agent_email = contact.get("email")
        agent_id = agent_info.get("id")

    return FDKContext(
        domain=domain,
        api_key=api_key,
        tenant_id=tenant_id,
        verified=True,
        agent_email=agent_email,
        agent_id=agent_id,
    )


async def get_optional_fdk_context(request: Request) -> Optional[FDKContext]:
    """
    선택적 FDK 인증 컨텍스트

    헤더가 없으면 None 반환, 있으면 검증 수행

    Returns:
        FDKContext 또는 None
    """
    domain = request.headers.get("X-Freshdesk-Domain", "").strip()
    api_key = request.headers.get("X-Freshdesk-API-Key", "").strip()

    if not domain or not api_key:
        return None

    return await get_fdk_context(request)


async def get_fdk_context_no_verify(request: Request) -> FDKContext:
    """
    검증 없이 FDK 컨텍스트 추출

    API 키 검증을 건너뛰고 헤더 값만 추출
    (내부 서비스 간 호출이나 개발 환경에서 사용)

    Returns:
        FDKContext (verified=False)
    """
    domain = request.headers.get("X-Freshdesk-Domain", "").strip()
    api_key = request.headers.get("X-Freshdesk-API-Key", "").strip()
    tenant_id = request.headers.get("X-Tenant-ID", "").strip()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Freshdesk-Domain 헤더가 필요합니다",
        )

    if not tenant_id:
        tenant_id = extract_tenant_from_domain(domain)

    return FDKContext(
        domain=domain,
        api_key=api_key,
        tenant_id=tenant_id,
        verified=False,
    )
