"""
Analysis Persistence Layer

Saves analysis runs and ticket analyses to Supabase.
Provides history lookup and metrics tracking.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnalysisPersistence:
    """
    Handles persistence of analysis runs to Supabase.

    Tables:
    - analysis_runs: Audit log of all analysis attempts
    - ticket_analyses: Successful analysis results
    """

    def __init__(self, supabase_client: Optional[Any] = None):
        """
        Initialize persistence layer.

        Args:
            supabase_client: Optional Supabase client. If None, will use
                            get_supabase_client() on first access.
        """
        self._client = supabase_client
        self._initialized = False

    def _get_client(self) -> Optional[Any]:
        """Lazy-initialize Supabase client."""
        if self._client is not None:
            return self._client

        if self._initialized:
            return None

        try:
            from app.core.config import get_settings
            from supabase import create_client

            settings = get_settings()
            if settings.supabase_common_url and settings.supabase_common_service_role_key:
                self._client = create_client(
                    settings.supabase_common_url,
                    settings.supabase_common_service_role_key
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase client: {e}")

        self._initialized = True
        return self._client

    async def save_analysis_run(
        self,
        analysis_id: str,
        tenant_id: str,
        ticket_id: str,
        status: str = "running",
        gate: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Save or update an analysis run record.

        Args:
            analysis_id: UUID for this analysis run
            tenant_id: Tenant identifier
            ticket_id: Ticket being analyzed
            status: running | completed | failed
            gate: Gate decision if completed
            meta: Execution metadata
            error_message: Error details if failed

        Returns:
            True if saved successfully, False otherwise
        """
        client = self._get_client()
        if not client:
            logger.debug("Supabase client not configured, skipping persistence")
            return False

        try:
            now = datetime.now(timezone.utc).isoformat()
            run_data = {
                "id": analysis_id,
                "tenant_id": tenant_id,
                "ticket_id": ticket_id,
                "status": status,
                "gate": gate,
                "meta": meta or {},
                "error_message": error_message,
                "created_at": now,
            }

            if status in ("completed", "failed"):
                run_data["completed_at"] = now

            client.table("analysis_runs").upsert(run_data).execute()
            logger.info(f"Analysis run saved: {analysis_id} status={status}")
            return True

        except Exception as e:
            logger.error(f"Failed to save analysis run: {e}", exc_info=True)
            return False

    async def save_analysis_result(
        self,
        analysis_id: str,
        tenant_id: str,
        ticket_id: str,
        analysis: Dict[str, Any],
    ) -> bool:
        """
        Save successful analysis result.

        Args:
            analysis_id: UUID linking to analysis_runs
            tenant_id: Tenant identifier
            ticket_id: Analyzed ticket ID
            analysis: Full analysis object from LLM

        Returns:
            True if saved successfully, False otherwise
        """
        client = self._get_client()
        if not client:
            return False

        try:
            now = datetime.now(timezone.utc).isoformat()

            # Extract narrative safely
            narrative = analysis.get("narrative", {})
            if isinstance(narrative, dict):
                narrative_text = narrative.get("summary", "")
            else:
                narrative_text = str(narrative) if narrative else ""

            analysis_data = {
                "id": analysis_id,
                "run_id": analysis_id,
                "tenant_id": tenant_id,
                "ticket_id": ticket_id,
                "narrative": narrative_text,
                "root_cause": analysis.get("root_cause"),
                "resolution": analysis.get("resolution", []),
                "confidence": analysis.get("confidence", 0.0),
                "intent": analysis.get("intent"),
                "sentiment": analysis.get("sentiment"),
                "open_questions": analysis.get("open_questions", []),
                "risk_tags": analysis.get("risk_tags", []),
                "field_proposals": analysis.get("field_proposals", []),
                "evidence": analysis.get("evidence", []),
                "created_at": now,
            }

            client.table("ticket_analyses").upsert(analysis_data).execute()
            logger.info(f"Analysis result saved: {analysis_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save analysis result: {e}", exc_info=True)
            return False

    async def get_analysis_history(
        self,
        tenant_id: str,
        ticket_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get analysis history for a ticket.

        Args:
            tenant_id: Tenant identifier
            ticket_id: Ticket to get history for
            limit: Maximum records to return

        Returns:
            List of past analysis runs with summary info
        """
        client = self._get_client()
        if not client:
            return []

        try:
            result = client.table("analysis_runs") \
                .select("id, status, gate, created_at, completed_at, meta") \
                .eq("tenant_id", tenant_id) \
                .eq("ticket_id", ticket_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get analysis history: {e}")
            return []

    async def get_analysis_by_id(
        self,
        analysis_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific analysis by ID.

        Args:
            analysis_id: Analysis UUID
            tenant_id: Tenant identifier (for security)

        Returns:
            Full analysis record or None if not found
        """
        client = self._get_client()
        if not client:
            return None

        try:
            result = client.table("ticket_analyses") \
                .select("*") \
                .eq("id", analysis_id) \
                .eq("tenant_id", tenant_id) \
                .single() \
                .execute()

            return result.data

        except Exception as e:
            logger.error(f"Failed to get analysis: {e}")
            return None


# Singleton instance
_persistence: Optional[AnalysisPersistence] = None


def get_analysis_persistence() -> AnalysisPersistence:
    """Get singleton persistence instance."""
    global _persistence
    if _persistence is None:
        _persistence = AnalysisPersistence()
    return _persistence
