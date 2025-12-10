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

    async def analyze_ticket(self, ticket_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ticket for intent, sentiment, and summary"""
        system_prompt = """
        You are an expert customer support analyzer. Analyze the ticket and return JSON with:
        - intent: (inquiry, complaint, request, technical_issue)
        - sentiment: (positive, neutral, negative, urgent)
        - summary: 1-sentence summary in Korean
        - key_entities: list of important entities
        """
        
        user_prompt = json.dumps(ticket_context, ensure_ascii=False)
        
        response = await self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            json_mode=True
        )
        return json.loads(response)

    async def propose_solution(
        self, 
        ticket_context: Dict[str, Any], 
        search_results: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate draft response and field updates"""
        system_prompt = """
        You are a helpful support agent. Based on the ticket and search results, 
        generate a response draft and suggest field updates.
        
        Return JSON with:
        - draft_response: Polite, helpful response in Korean
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
