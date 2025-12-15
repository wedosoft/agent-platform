"""
LLM Adapter Service

Provides a unified interface for different LLM providers (DeepSeek, OpenAI).
Handles model selection and API communication.
"""
import logging
from typing import Optional, Dict, Any, List
import json
import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_nested_leaf_paths(choices: Any) -> List[List[str]]:
    """Build all valid paths from Freshdesk nested_field 'choices'.

    Freshdesk nested_field choices can be a mixed structure:
    - dict: {L1: {L2: [L3, ...]}} or {L1: {}}
    - list: [L3, ...] or [] (meaning leaf ends at current level)

    Returns a list of paths (each path is list[str]), where the leaf is the last element.
    """

    paths: List[List[str]] = []

    def walk(node: Any, prefix: List[str]) -> None:
        if node is None:
            return

        if isinstance(node, dict):
            if not node:
                # Leaf ends at current prefix (e.g., L1 leaf)
                if prefix:
                    paths.append(prefix)
                return
            for k, v in node.items():
                walk(v, prefix + [str(k)])
            return

        if isinstance(node, list):
            if len(node) == 0:
                # Leaf ends at current prefix (e.g., L2 leaf)
                if prefix:
                    paths.append(prefix)
                return
            for item in node:
                paths.append(prefix + [str(item)])
            return

        # Fallback: treat scalar as leaf
        paths.append(prefix + [str(node)])

    walk(choices, [])
    # Remove duplicates while preserving order
    seen = set()
    uniq: List[List[str]] = []
    for p in paths:
        key = tuple(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _pick_best_nested_path(subject: str, description: str, paths: List[List[str]]) -> Optional[List[str]]:
    """Pick the best matching nested path using simple rules + substring match.

    This exists to prevent obvious misclassification like Freshdesk tickets -> Splashtop.
    """
    text = f"{subject}\n{description}".lower()
    if not text.strip() or not paths:
        return None

    # Helper: find a path containing a specific leaf or segment.
    def find_path_containing(token: str) -> Optional[List[str]]:
        tok = token.lower()
        candidates = [p for p in paths if any(seg.lower() == tok for seg in p)]
        if not candidates:
            return None
        # Prefer longer (more specific) paths
        candidates.sort(key=lambda p: (len(p), sum(len(s) for s in p)), reverse=True)
        return candidates[0]

    # Strong keyword rules (Korean/English synonyms)
    # Freshdesk (헬프데스크/티켓 필드/포털 등)
    if any(k in text for k in ["freshdesk", "헬프데스크", "helpdesk", "ticket field", "티켓 필드", "언어 관리", "번역", "yml", "yaml"]):
        # Try to map to Freshworks Suite > Freshdesk
        p = find_path_containing("Freshdesk")
        if p:
            return p

    if any(k in text for k in ["freshservice"]):
        p = find_path_containing("Freshservice")
        if p:
            return p

    if any(k in text for k in ["freshsales"]):
        p = find_path_containing("Freshsales (Suite)") or find_path_containing("Freshsales")
        if p:
            return p

    if any(k in text for k in ["freshchat", "freddy", "bot", "프레디", "챗봇"]):
        p = find_path_containing("Freshchat/Freddy Bot")
        if p:
            return p

    if "splashtop" in text:
        p = find_path_containing("Splashtop")
        if p:
            return p

    if any(k in text for k in ["google workspace", "g suite", "gmail", "google drive", "구글", "지메일", "드라이브", "캘린더"]):
        # Prefer most specific Google leaf if present
        for leaf in ["Gmail", "Google Drive", "Google Calendar", "Control Panel", "Google Workspace"]:
            p = find_path_containing(leaf)
            if p:
                return p

    if any(k in text for k in ["spanning"]):
        p = find_path_containing("Spanning Backup")
        if p:
            return p

    # Generic: choose the longest leaf whose segment appears as substring
    scored: List[tuple[int, int, List[str]]] = []
    for p in paths:
        leaf = p[-1].lower()
        if leaf and leaf in text:
            scored.append((len(leaf), len(p), p))
    if scored:
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return scored[0][2]

    return None


def _upsert_field_proposal(
    proposals: List[Dict[str, Any]],
    field_name: str,
    field_label: str,
    proposed_value: Any,
    reason: str,
) -> List[Dict[str, Any]]:
    # Remove existing entries for same field_name
    out = [p for p in proposals if p.get("field_name") != field_name]
    out.append(
        {
            "field_name": field_name,
            "field_label": field_label,
            "proposed_value": proposed_value,
            "reason": reason,
        }
    )
    return out

class LLMAdapter:
    def __init__(self):
        self.settings = get_settings()
        self.provider = self.settings.llm_provider.lower()
        self.api_key = (
            self.settings.deepseek_api_key 
            if self.provider == "deepseek" 
            else self.settings.openai_api_key
        )
        
        if not self.api_key:
            logger.warning(f"API Key for {self.provider} is missing!")

        # Initialize OpenAI client (DeepSeek is OpenAI-compatible)
        base_url = "https://api.deepseek.com" if self.provider == "deepseek" else None
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)
        
        # Model selection
        if self.provider == "deepseek":
            self.model = "deepseek-chat"  # DeepSeek V3
        else:
            self.model = "gpt-4o-mini"  # Default OpenAI model

    async def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        """Generate text response from LLM"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"} if json_mode else None
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Generation Error ({self.provider}): {e}")
            raise

    async def analyze_ticket(self, ticket_context: Dict[str, Any], response_tone: str = "formal") -> Dict[str, Any]:
        """Analyze ticket for intent, sentiment, summary, and field proposals"""
        
        # Handle both snake_case and camelCase keys (due to Pydantic aliases)
        ticket_fields = ticket_context.get("ticket_fields") or ticket_context.get("ticketFields") or []
        
        system_prompt = f"""
        You are an expert customer support analyzer. Analyze the ticket and return JSON with:
        - intent: (inquiry, complaint, request, technical_issue)
        - sentiment: (positive, neutral, negative, urgent)
        - summary: 1-sentence summary in Korean ({response_tone} tone)
        - key_entities: list of important entities
        - field_proposals: List of suggested field updates based on the provided schema.
          Each proposal must include:
          - field_name: The API name of the field (from schema)
          - field_label: The display label of the field
          - proposed_value: The value to set (must match schema choices if applicable)
          - reason: A clear explanation in Korean ({response_tone} tone) why this value is proposed.

        IMPORTANT: 
        - Only propose updates for fields defined in the 'ticket_fields_schema' below.
        - Pay special attention to nested fields (fields with 'choices' that have sub-choices).
        - For nested fields, propose the leaf value if possible, or the appropriate level value.
        
        Ticket Fields Schema:
        {json.dumps(ticket_fields, ensure_ascii=False, indent=2)}
        """
        
        # Remove ticket_fields from user_prompt to save tokens, as it's in system prompt
        context_copy = ticket_context.copy()
        context_copy.pop("ticket_fields", None)
        context_copy.pop("ticketFields", None)
        
        user_prompt = json.dumps(context_copy, ensure_ascii=False)
        
        response = await self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            json_mode=True
        )

        result = json.loads(response)

        # --- Post-processing: prevent mismatched nested field suggestions ---
        try:
            subject = (ticket_context.get("subject") or "")
            description = (ticket_context.get("description") or ticket_context.get("description_text") or "")

            # Find the first nested_field root (current UI supports one main nested field)
            nested_roots = [f for f in ticket_fields if isinstance(f, dict) and f.get("type") == "nested_field"]
            if nested_roots:
                root = nested_roots[0]
                root_name = root.get("name")
                root_label = root.get("label") or root.get("label_for_customers") or root_name
                nested_fields = root.get("nested_ticket_fields") or []
                level2 = next((nf for nf in nested_fields if nf.get("level") == 2), None)
                level3 = next((nf for nf in nested_fields if nf.get("level") == 3), None)

                paths = _build_nested_leaf_paths(root.get("choices"))
                best = _pick_best_nested_path(subject, description, paths)

                if best and root_name:
                    proposals = result.get("field_proposals") or []
                    if not isinstance(proposals, list):
                        proposals = []

                    reason = "티켓 내용의 키워드와 중첩 필드 선택지 트리를 기반으로 카테고리를 보정했습니다."

                    # Always set root (level1)
                    proposals = _upsert_field_proposal(
                        proposals,
                        field_name=root_name,
                        field_label=str(root_label),
                        proposed_value=best[0],
                        reason=reason,
                    )

                    # Optionally set level2/level3
                    if level2 and len(best) >= 2:
                        proposals = _upsert_field_proposal(
                            proposals,
                            field_name=str(level2.get("name")),
                            field_label=str(level2.get("label") or level2.get("label_in_portal") or level2.get("name")),
                            proposed_value=best[1],
                            reason=reason,
                        )
                    if level3 and len(best) >= 3:
                        proposals = _upsert_field_proposal(
                            proposals,
                            field_name=str(level3.get("name")),
                            field_label=str(level3.get("label") or level3.get("label_in_portal") or level3.get("name")),
                            proposed_value=best[2],
                            reason=reason,
                        )

                    result["field_proposals"] = proposals

        except Exception as e:
            logger.warning(f"Nested field post-processing skipped due to error: {e}")

        return result

    async def propose_solution(
        self, 
        ticket_context: Dict[str, Any], 
        search_results: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate solution analysis and field updates"""
        system_prompt = """
        You are a helpful support agent. Based on the ticket and search results, 
        analyze the root cause and provide a solution.
        
        Return JSON with:
        - cause: The root cause of the issue in Korean (1-2 sentences)
        - solution: A brief solution or next steps in Korean (bullet points allowed)
        - field_updates: { priority, status, type, tags } (only if changes needed)
        - reasoning: Why you made these suggestions
        """
        
        context = {
            "ticket": ticket_context,
            "analysis": analysis_result,
            "similar_cases": search_results.get("similar_cases", []),
            "kb_articles": search_results.get("kb_procedures", [])
        }
        
        response = await self.generate(
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, ensure_ascii=False),
            temperature=0.7,
            json_mode=True
        )
        return json.loads(response)
