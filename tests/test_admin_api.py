"""
Admin API 테스트

테넌트 관리, 동기화, 스케줄러 API 엔드포인트 테스트
"""

import pytest
from typing import Callable, List, Optional
from fastapi.testclient import TestClient

from app.main import app
from app.services.admin_service import AdminService, get_admin_service
from app.models.admin import SchedulerJobInfo


# =============================================================================
# Fixtures
# =============================================================================

# 테스트용 Admin API 키
TEST_ADMIN_API_KEY = "test-admin-key-12345"


class MockSchedulerService:
    """테스트용 Mock SchedulerService"""

    def __init__(self):
        self._jobs = {}
        self._job_metadata = {}
        self._execution_history = {}
        self._running = False  # 테스트에서는 시작하지 않음
        self._job_counter = 0

    def is_running(self) -> bool:
        return self._running

    def start(self):
        self._running = True

    def shutdown(self, wait: bool = True):
        self._running = False

    def list_jobs(self, tenant_id: Optional[str] = None) -> List[SchedulerJobInfo]:
        """작업 목록 조회"""
        jobs = []
        for job_id, metadata in self._job_metadata.items():
            if tenant_id is None or metadata.get("tenant_id") == tenant_id:
                jobs.append(SchedulerJobInfo(
                    job_id=job_id,
                    tenant_id=metadata["tenant_id"],
                    job_type=metadata["job_type"],
                    cron_expression=metadata["cron_expression"],
                    next_run_time=None,
                    last_run_time=None,
                    enabled=metadata.get("enabled", True),
                ))
        return jobs

    def add_job(
        self,
        tenant_id: str,
        job_type: str,
        cron_expression: str,
        handler: Callable,
        enabled: bool = True,
    ) -> SchedulerJobInfo:
        """작업 추가"""
        import uuid
        job_id = str(uuid.uuid4())

        self._job_metadata[job_id] = {
            "tenant_id": tenant_id,
            "job_type": job_type,
            "cron_expression": cron_expression,
            "enabled": enabled,
        }

        return SchedulerJobInfo(
            job_id=job_id,
            tenant_id=tenant_id,
            job_type=job_type,
            cron_expression=cron_expression,
            next_run_time=None,
            last_run_time=None,
            enabled=enabled,
        )

    def remove_job(self, job_id: str) -> None:
        """작업 삭제"""
        if job_id not in self._job_metadata:
            raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")
        del self._job_metadata[job_id]

    def toggle_job(self, job_id: str, enabled: bool) -> SchedulerJobInfo:
        """작업 활성화/비활성화"""
        if job_id not in self._job_metadata:
            raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")

        self._job_metadata[job_id]["enabled"] = enabled
        metadata = self._job_metadata[job_id]

        return SchedulerJobInfo(
            job_id=job_id,
            tenant_id=metadata["tenant_id"],
            job_type=metadata["job_type"],
            cron_expression=metadata["cron_expression"],
            next_run_time=None,
            last_run_time=None,
            enabled=enabled,
        )


class MockAdminService(AdminService):
    """테스트용 Mock AdminService"""

    def __init__(self):
        from app.services.admin_service import TenantStore, SyncJobStore
        self.tenant_store = TenantStore()
        self.sync_job_store = SyncJobStore()
        self.scheduler_service = MockSchedulerService()
        self.admin_api_key = TEST_ADMIN_API_KEY


@pytest.fixture
def mock_admin_service():
    """Mock AdminService 주입"""
    mock = MockAdminService()
    app.dependency_overrides[get_admin_service] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_admin_service, None)


@pytest.fixture
def admin_client(mock_admin_service) -> TestClient:
    """테스트 클라이언트"""
    return TestClient(app)


def admin_headers():
    """관리자 헤더"""
    return {"X-Admin-API-Key": TEST_ADMIN_API_KEY}


# =============================================================================
# Tenant CRUD Tests
# =============================================================================

class TestTenantCRUD:
    """테넌트 CRUD 테스트"""

    def test_list_tenants_empty(self, admin_client):
        """빈 테넌트 목록 조회"""
        response = admin_client.get(
            "/api/admin/tenants",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenants"] == []
        assert data["total"] == 0

    def test_create_tenant(self, admin_client):
        """테넌트 생성"""
        response = admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test-company.freshdesk.com",
                "freshdesk_api_key": "secret-api-key-12345",
                "embedding_enabled": True,
            },
            headers=admin_headers(),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["tenant"]["tenant_id"] == "test-company"
        # API 키가 마스킹되었는지 확인
        assert "****" in data["tenant"]["freshdesk_api_key"]

    def test_get_tenant(self, admin_client):
        """테넌트 조회"""
        # 먼저 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test-company.freshdesk.com",
                "freshdesk_api_key": "secret-key",
            },
            headers=admin_headers(),
        )

        # 조회
        response = admin_client.get(
            "/api/admin/tenants/test-company",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test-company"

    def test_get_tenant_not_found(self, admin_client):
        """존재하지 않는 테넌트 조회"""
        response = admin_client.get(
            "/api/admin/tenants/non-existent",
            headers=admin_headers(),
        )

        assert response.status_code == 404

    def test_update_tenant(self, admin_client):
        """테넌트 수정"""
        # 먼저 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test-company.freshdesk.com",
                "freshdesk_api_key": "secret-key",
            },
            headers=admin_headers(),
        )

        # 수정
        response = admin_client.put(
            "/api/admin/tenants/test-company",
            json={
                "embedding_enabled": False,
                "llm_max_tokens": 2000,
            },
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["tenant"]["embedding_enabled"] is False
        assert data["tenant"]["llm_max_tokens"] == 2000

    def test_delete_tenant(self, admin_client):
        """테넌트 삭제"""
        # 먼저 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test-company.freshdesk.com",
                "freshdesk_api_key": "secret-key",
            },
            headers=admin_headers(),
        )

        # 삭제
        response = admin_client.delete(
            "/api/admin/tenants/test-company",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # 삭제 확인
        get_response = admin_client.get(
            "/api/admin/tenants/test-company",
            headers=admin_headers(),
        )
        assert get_response.status_code == 404

    def test_create_duplicate_tenant(self, admin_client):
        """중복 테넌트 생성 시 에러"""
        tenant_data = {
            "tenant_id": "test-company",
            "freshdesk_domain": "test-company.freshdesk.com",
            "freshdesk_api_key": "secret-key",
        }

        # 첫 번째 생성
        admin_client.post(
            "/api/admin/tenants",
            json=tenant_data,
            headers=admin_headers(),
        )

        # 중복 생성 시도
        response = admin_client.post(
            "/api/admin/tenants",
            json=tenant_data,
            headers=admin_headers(),
        )

        assert response.status_code == 409  # Conflict


# =============================================================================
# Authentication Tests
# =============================================================================

class TestAdminAuth:
    """관리자 인증 테스트"""

    def test_missing_api_key(self, admin_client):
        """API 키 누락 시 에러"""
        response = admin_client.get("/api/admin/tenants")

        assert response.status_code == 422  # Missing header

    def test_invalid_api_key(self, admin_client):
        """잘못된 API 키 시 에러"""
        response = admin_client.get(
            "/api/admin/tenants",
            headers={"X-Admin-API-Key": "wrong-key"},
        )

        assert response.status_code == 401


# =============================================================================
# Sync Endpoint Tests
# =============================================================================

class TestSyncEndpoints:
    """동기화 엔드포인트 테스트"""

    def test_get_sync_status(self, admin_client):
        """동기화 상태 조회"""
        # 테넌트 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test.freshdesk.com",
                "freshdesk_api_key": "key",
            },
            headers=admin_headers(),
        )

        response = admin_client.get(
            "/api/admin/tenants/test-company/sync/status",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test-company"
        assert "sync_in_progress" in data

    def test_trigger_sync(self, admin_client):
        """동기화 트리거"""
        # 테넌트 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test.freshdesk.com",
                "freshdesk_api_key": "key",
            },
            headers=admin_headers(),
        )

        response = admin_client.post(
            "/api/admin/tenants/test-company/sync/trigger",
            json={
                "sync_type": "all",
                "limit": 100,
            },
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data


# =============================================================================
# Scheduler Endpoint Tests
# =============================================================================

class TestSchedulerEndpoints:
    """스케줄러 엔드포인트 테스트"""

    def test_get_scheduler_status(self, admin_client):
        """스케줄러 상태 조회"""
        response = admin_client.get(
            "/api/admin/scheduler/status",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "jobs" in data

    def test_create_scheduler_job(self, admin_client):
        """스케줄러 작업 생성"""
        # 테넌트 생성
        admin_client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "test-company",
                "freshdesk_domain": "test.freshdesk.com",
                "freshdesk_api_key": "key",
            },
            headers=admin_headers(),
        )

        response = admin_client.post(
            "/api/admin/scheduler/jobs",
            json={
                "tenant_id": "test-company",
                "job_type": "sync_all",
                "cron_expression": "0 */6 * * *",
                "enabled": True,
            },
            headers=admin_headers(),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert "job" in data

    def test_create_scheduler_job_invalid_tenant(self, admin_client):
        """존재하지 않는 테넌트로 작업 생성 시 에러"""
        response = admin_client.post(
            "/api/admin/scheduler/jobs",
            json={
                "tenant_id": "non-existent",
                "job_type": "sync_all",
                "cron_expression": "0 */6 * * *",
            },
            headers=admin_headers(),
        )

        assert response.status_code == 400


# =============================================================================
# Cache Endpoint Tests
# =============================================================================

class TestCacheEndpoints:
    """캐시 엔드포인트 테스트"""

    def test_clear_cache(self, admin_client):
        """캐시 클리어"""
        response = admin_client.post(
            "/api/admin/cache/clear",
            headers=admin_headers(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cache_cleared"
        assert "timestamp" in data
