import pytest


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def ilike(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _FakeResponse(self._data)


class _FakeClient:
    def __init__(self, data):
        self._data = data

    def table(self, *_args, **_kwargs):
        return _FakeQuery(self._data)


@pytest.mark.asyncio
async def test_get_session_by_user_name_returns_session_when_single_record():
    # Arrange: exactly one session exists
    from app.services.onboarding_repository import OnboardingRepository

    one = [
        {
            "id": 123,
            "session_id": "sess_1",
            "user_name": "Alice",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]
    repo = OnboardingRepository(client=_FakeClient(one))

    # Act
    session = await repo.get_session_by_user_name("Alice")

    # Assert: should NOT be None
    assert session is not None
    assert session.sessionId == "sess_1"


