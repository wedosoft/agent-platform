"""온보딩 프롬프트 로더 - YAML 템플릿 기반 프롬프트 관리."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.prompts.loader import load_prompt

LOGGER = logging.getLogger(__name__)

_MENTOR_PROMPT_SPEC = None
_FEEDBACK_PROMPT_SPEC = None
_QUIZ_PROMPT_SPEC = None


def _get_mentor_prompt_spec():
    """멘토 채팅 프롬프트 스펙 로드 (캐싱)."""
    global _MENTOR_PROMPT_SPEC
    if _MENTOR_PROMPT_SPEC is None:
        try:
            _MENTOR_PROMPT_SPEC = load_prompt("mentor_chat")
        except Exception as e:
            LOGGER.warning(f"Failed to load mentor_chat prompt: {e}")
            return None
    return _MENTOR_PROMPT_SPEC


def _get_feedback_prompt_spec():
    """피드백 프롬프트 스펙 로드 (캐싱)."""
    global _FEEDBACK_PROMPT_SPEC
    if _FEEDBACK_PROMPT_SPEC is None:
        try:
            _FEEDBACK_PROMPT_SPEC = load_prompt("feedback")
        except Exception as e:
            LOGGER.warning(f"Failed to load feedback prompt: {e}")
            return None
    return _FEEDBACK_PROMPT_SPEC


def _get_quiz_prompt_spec():
    """퀴즈 생성 프롬프트 스펙 로드 (캐싱)."""
    global _QUIZ_PROMPT_SPEC
    if _QUIZ_PROMPT_SPEC is None:
        try:
            _QUIZ_PROMPT_SPEC = load_prompt("quiz_generation")
        except Exception as e:
            LOGGER.warning(f"Failed to load quiz_generation prompt: {e}")
            return None
    return _QUIZ_PROMPT_SPEC


MENTOR_SYSTEM_PROMPT_FALLBACK = """당신은 신입사원을 돕는 친절하고 전문적인 시니어 멘토 '온보딩 나침반'입니다.

당신의 특징:
- 친절하고 부드러운 '해요체' 사용 (예: ~해요, ~입니다)
- 신입사원의 입장을 이해하고 공감하는 태도
- 실질적이고 실행 가능한 조언을 알기 쉽게 설명
- 생산성, 시간 관리, 커뮤니케이션, 문제 해결, 협업에 대한 전문 지식
- 한국어로 답변

질문에 대해 친절하게 설명하고, 신입사원이 업무에 잘 적응할 수 있도록 격려와 구체적인 가이드를 함께 제공하세요."""


def get_mentor_system_prompt(
    rag_context: Optional[str] = None,
    conversation_summary: Optional[str] = None,
) -> str:
    """멘토 시스템 프롬프트 생성."""
    spec = _get_mentor_prompt_spec()
    if spec is None:
        return MENTOR_SYSTEM_PROMPT_FALLBACK
    
    try:
        rendered = spec.render(
            rag_context=rag_context,
            conversation_summary=conversation_summary,
        )
        return rendered.system_prompt or MENTOR_SYSTEM_PROMPT_FALLBACK
    except Exception as e:
        LOGGER.warning(f"Failed to render mentor system prompt: {e}")
        return MENTOR_SYSTEM_PROMPT_FALLBACK


def get_mentor_user_prompt(
    user_message: str,
    user_name: Optional[str] = None,
    scenario_context: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """멘토 사용자 프롬프트 생성."""
    spec = _get_mentor_prompt_spec()
    if spec is None:
        return user_message
    
    try:
        rendered = spec.render(
            user_message=user_message,
            user_name=user_name,
            scenario_context=scenario_context,
            conversation_history=conversation_history,
        )
        return rendered.user_prompt or user_message
    except Exception as e:
        LOGGER.warning(f"Failed to render mentor user prompt: {e}")
        return user_message


FEEDBACK_PROMPT_FALLBACK = """당신은 글로벌 최상위 테크 기업의 노련한 시니어 매니저입니다.

업무 시나리오:
**제목:** {scenario_title}
**상황:** {scenario_description}

선택 가능한 행동들:
{all_choices_text}

**선택한 행동:** "{selected_choice}"

이 선택에 대해 명확하고 실행 가능한 피드백을 제공해 주세요.
**중요: 이름을 부르거나 인사말 없이 바로 본론으로 들어가세요.**
**피드백은 반드시 아래의 마크다운 서식을 정확히 따라야 합니다.**

### 🤷 선택에 대한 분석
(선택을 인정하고, 실제 업무 환경에서 가질 수 있는 장점과 단점을 균형 있게 분석)

---

### 💡 추천하는 접근 방식
(이 시나리오에 적용할 수 있는 가장 효과적인 업무 원칙이나 사고 모델 설명. 가장 이상적인 행동과 그 이유를 명확히 제시)

---

### 🤔 다른 선택지들에 대한 고찰
(선택되지 않은 다른 옵션들이 왜 덜 효과적인지 간략하게 설명)

---

### ⭐ 핵심 정리
> (앞으로 유사한 상황에서 기억하고 적용할 수 있는 핵심 원칙이나 교훈을 blockquote 형식으로 작성)

**피드백 작성이 끝나면, 반드시 다음 줄에 %%%QUESTIONS%%% 라는 구분자를 삽입해주세요.**

그 다음 줄부터, 이 주제에 대해 더 깊이 생각해볼 수 있는 3개의 연관 질문을 각각 한 줄씩 작성해주세요. 질문 앞에는 번호나 글머리 기호를 붙이지 마세요."""


def get_feedback_prompt(
    user_name: str,
    scenario_title: str,
    scenario_description: str,
    all_choices: List[str],
    selected_choice: str,
    category_name: Optional[str] = None,
    is_recommended_choice: bool = False,
    recommended_choice_text: Optional[str] = None,
) -> str:
    """시나리오 피드백 생성을 위한 프롬프트."""
    spec = _get_feedback_prompt_spec()
    
    choices_data = [
        {"text": choice, "is_recommended": (choice == recommended_choice_text)}
        for choice in all_choices
    ]
    
    if spec is None:
        all_choices_text = '\n'.join(f'- {choice}' for choice in all_choices)
        return FEEDBACK_PROMPT_FALLBACK.format(
            scenario_title=scenario_title,
            scenario_description=scenario_description,
            all_choices_text=all_choices_text,
            selected_choice=selected_choice,
        )
    
    try:
        rendered = spec.render(
            user_name=user_name,
            scenario_title=scenario_title,
            scenario_description=scenario_description,
            choices=choices_data,
            selected_choice_text=selected_choice,
            category_name=category_name or "",
            is_recommended_choice=is_recommended_choice,
            recommended_choice_text=recommended_choice_text or "",
        )
        
        prompt = rendered.user_prompt or ""
        if rendered.system_prompt:
            prompt = f"{rendered.system_prompt}\n\n{prompt}"
        
        prompt += """

**피드백 작성이 끝나면, 반드시 다음 줄에 %%%QUESTIONS%%% 라는 구분자를 삽입해주세요.**

그 다음 줄부터, 이 주제에 대해 더 깊이 생각해볼 수 있는 3개의 연관 질문을 각각 한 줄씩 작성해주세요. 질문 앞에는 번호나 글머리 기호를 붙이지 마세요."""
        
        return prompt
    except Exception as e:
        LOGGER.warning(f"Failed to render feedback prompt: {e}")
        all_choices_text = '\n'.join(f'- {choice}' for choice in all_choices)
        return FEEDBACK_PROMPT_FALLBACK.format(
            scenario_title=scenario_title,
            scenario_description=scenario_description,
            all_choices_text=all_choices_text,
            selected_choice=selected_choice,
        )


FOLLOWUP_PROMPT_FALLBACK = """당신은 글로벌 최상위 테크 기업의 시니어 멘토입니다.

**상황:**
- **시나리오:** {scenario_title} ({scenario_description})
- **이전 조언 요약:** {original_feedback}...

**추가 질문:** "{question}"

이 질문에 대해 명확하고, 실질적이며, 실행 가능한 답변을 해주세요.
**중요: 이름을 부르거나 인사말 없이 바로 본론으로 들어가세요.**
답변은 마크다운 형식으로, 한국어로 해주세요."""


def get_followup_prompt(
    user_name: str,
    scenario_title: str,
    scenario_description: str,
    original_feedback: str,
    question: str
) -> str:
    """후속 질문 답변 생성을 위한 프롬프트."""
    return FOLLOWUP_PROMPT_FALLBACK.format(
        scenario_title=scenario_title,
        scenario_description=scenario_description,
        original_feedback=original_feedback[:500],
        question=question,
    )


def get_quiz_generation_prompt(
    module_title: str,
    product_name: str,
    learning_content: str,
    question_count: int = 5,
    category_name: Optional[str] = None,
    key_concepts: Optional[List[str]] = None,
    learning_objectives: Optional[List[str]] = None,
    difficulty_preference: Optional[str] = None,
    question_types: Optional[str] = None,
) -> Dict[str, str]:
    """퀴즈 생성 프롬프트 반환 (system_prompt, user_prompt)."""
    spec = _get_quiz_prompt_spec()
    
    if spec is None:
        return {
            "system_prompt": "You are an educational content expert. Generate quiz questions based on the learning material.",
            "user_prompt": f"Generate {question_count} quiz questions for the module '{module_title}' about {product_name}.\n\nContent:\n{learning_content}",
        }
    
    try:
        rendered = spec.render(
            module_title=module_title,
            product_name=product_name,
            learning_content=learning_content,
            question_count=question_count,
            category_name=category_name,
            key_concepts=key_concepts,
            learning_objectives=learning_objectives,
            difficulty_preference=difficulty_preference,
            question_types=question_types,
        )
        return {
            "system_prompt": rendered.system_prompt or "",
            "user_prompt": rendered.user_prompt or "",
        }
    except Exception as e:
        LOGGER.warning(f"Failed to render quiz generation prompt: {e}")
        return {
            "system_prompt": "You are an educational content expert. Generate quiz questions based on the learning material.",
            "user_prompt": f"Generate {question_count} quiz questions for the module '{module_title}' about {product_name}.\n\nContent:\n{learning_content}",
        }
