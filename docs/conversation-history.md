# 대화 히스토리 처리 로직

> 작성일: 2025-11-26  
> 관련 파일: `app/services/session_repository.py`, `app/api/routes/chat.py`, `app/services/gemini_file_search_client.py`

## 1. 개요

Gemini File Search API를 사용한 RAG 챗봇에서 **멀티턴 대화**(연속 질문)를 지원하기 위한 히스토리 처리 로직입니다.

### 문제 상황
```
사용자: "구성관리자에 대해 더 자세히 알려줘"
AI: (구성 관리자 설명)

사용자: "주로 어느 용도로 사용돼?"
AI: ❌ Freshservice 전체 용도를 설명 (맥락 손실)
AI: ✅ 구성 관리자의 용도를 설명 (맥락 유지)
```

### 원인
- 이전 구현: 질문(`user`)만 히스토리에 저장 → Gemini가 모든 히스토리를 새 질문으로 인식
- 수정 구현: 질문(`user`) + 답변(`model`) 쌍으로 저장 → Gemini가 대화 맥락 파악

---

## 2. 데이터 구조

### 세션 저장소 (`SessionRecord`)

```python
{
    "sessionId": "uuid-string",
    "createdAt": "2025-11-26T00:00:00Z",
    "updatedAt": "2025-11-26T00:01:00Z",
    
    # 레거시 (이전 버전 호환용)
    "questionHistory": ["질문1", "질문2", ...],
    
    # 새 구조 (user/model 역할 포함)
    "conversationHistory": [
        {"role": "user", "text": "구성관리자에 대해 더 자세히 알려줘"},
        {"role": "model", "text": "Freshservice에서 구성 관리자 역할은..."},
        {"role": "user", "text": "주로 어느 용도로 사용돼?"},
        {"role": "model", "text": "구성 관리자는 주로 CMDB와 자산 관리에..."},
    ]
}
```

### Gemini API `contents` 형식

```python
[
    {"role": "user", "parts": [{"text": "질문1"}]},
    {"role": "model", "parts": [{"text": "답변1"}]},
    {"role": "user", "parts": [{"text": "질문2"}]},  # 현재 질문
]
```

---

## 3. 핵심 코드

### 3.1 세션 저장소 - `append_turn()` 메서드

```python
# app/services/session_repository.py

async def append_turn(self, session_id: str, question: str, answer: str) -> Optional[SessionRecord]:
    """질문+답변 쌍을 대화 히스토리에 추가"""
    record = await self.get(session_id)
    if not record:
        return None
    
    turns = record.setdefault("conversationHistory", [])
    turns.append({"role": "user", "text": question})
    turns.append({"role": "model", "text": answer})
    
    # 컨텍스트 오버플로우 방지: 최근 10개 턴(5 Q&A 쌍)만 유지
    if len(turns) > 10:
        record["conversationHistory"] = turns[-10:]
    
    record["updatedAt"] = datetime.now(timezone.utc).isoformat()
    await self.save(record)
    return record
```

### 3.2 Chat API - 히스토리 전달 및 저장

```python
# app/api/routes/chat.py

@router.post("/chat")
async def chat(request: ChatRequest, ...):
    if common_handler and common_handler.can_handle(request):
        session = await repository.get(request.session_id)
        
        # conversationHistory 사용 (역할 정보 포함)
        conversation_history = []
        if session and isinstance(session, dict):
            conversation_history = session.get("conversationHistory", [])
        
        # Gemini에 히스토리와 함께 요청
        response = await common_handler.handle(request, history=conversation_history)
        
        # 질문 + 답변을 함께 저장
        await repository.append_turn(request.session_id, request.query, response.text or "")
        
        return response
```

### 3.3 Gemini 클라이언트 - `contents` 구성

```python
# app/services/gemini_file_search_client.py

def _build_contents(self, query: str, conversation_history: Optional[List[dict]] = None) -> List[Dict[str, Any]]:
    """user/model 역할을 올바르게 번갈아 구성"""
    contents: List[Dict[str, Any]] = []
    
    # 대화 히스토리 추가 (역할 유지)
    for turn in (conversation_history or []):
        if isinstance(turn, dict) and "role" in turn and "text" in turn:
            role = turn["role"]
            text = turn["text"]
            if role in ("user", "model") and text and text.strip():
                contents.append({
                    "role": role,
                    "parts": [{"text": text}],
                })
        elif isinstance(turn, str) and turn.strip():
            # 레거시 문자열 히스토리 폴백 (user로 처리)
            contents.append({
                "role": "user",
                "parts": [{"text": turn}],
            })
    
    # 현재 질문 추가
    contents.append({
        "role": "user",
        "parts": [{"text": query}],
    })
    
    return contents
```

---

## 4. 시스템 인스트럭션

```python
SYSTEM_INSTRUCTION = (
    "You are a helpful customer support assistant. "
    "Answer ONLY the user's CURRENT question based on the provided search results (Context). "
    "Do NOT repeat or re-answer previous questions from the conversation history. "
    "If the answer is not in the context, politely state that you cannot find the information. "
    "Keep your response focused and concise."
)
```

**핵심 지시사항:**
- `CURRENT question` - 현재 질문에만 답변
- `Do NOT repeat or re-answer previous questions` - 이전 답변 반복 금지

---

## 5. 히스토리 제한

| 설정 | 값 | 이유 |
|------|-----|------|
| 최대 턴 수 | 10 (5 Q&A) | 토큰 제한 및 응답 속도 |
| 스트리밍 모드 | 4 (2 Q&A) | 지연 시간 최소화 |

```python
# 일반 채팅
if len(turns) > 10:
    record["conversationHistory"] = turns[-10:]

# 스트리밍 채팅
if len(conversation_history) > 4:
    conversation_history = conversation_history[-4:]
```

---

## 6. 디버깅

### 로그 확인

서버 터미널에서 다음 로그 패턴 확인:

```
📝 Conversation history: 2 turns
  [0] user: 구성관리자에 대해 더 자세히 알려줘...
  [1] model: Freshservice에서 구성 관리자 역할은 주로 자산 관리에 중점을 둔 에...
  [2] user: 주로 어느 용도로 사용돼?...
```

### 체크리스트

1. **`0 turns`로 표시되는 경우:**
   - 세션이 새로 생성됨 (새 대화 스레드)
   - Redis/메모리 저장소가 초기화됨
   - `append_turn()` 호출 실패

2. **히스토리는 있지만 맥락이 안 되는 경우:**
   - 시스템 인스트럭션 확인
   - `role`이 올바르게 `user`/`model`로 번갈아 있는지 확인

---

## 7. 관련 파일

| 파일 | 역할 |
|------|------|
| `app/services/session_repository.py` | 세션 및 히스토리 저장 |
| `app/api/routes/chat.py` | Chat API 엔드포인트 |
| `app/services/common_chat_handler.py` | 공통 문서 챗 핸들러 |
| `app/services/gemini_file_search_client.py` | Gemini API 클라이언트 |

---

## 8. 향후 개선 사항

- [ ] 히스토리 요약 (긴 대화를 압축)
- [ ] 세션별 히스토리 TTL 설정
- [ ] 멀티 스토어 대화 (티켓 + 공통문서 혼합)
