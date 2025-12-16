from __future__ import annotations

from app.services.onboarding_repository import OnboardingRepository


def test_onboarding_repository_exposes_supabase_alias():
    client = object()
    repo = OnboardingRepository(client)  # type: ignore[arg-type]
    assert repo.client is client
    assert repo.supabase is client

