네. **PR0 작업지시서 완성본**을 아래처럼 드리겠습니다. 이 PR0는 “리뉴얼”이 아니라, **리뉴얼 전에 레포 상태를 그린(테스트 통과)으로 만들어 다음 PR들이 흔들리지 않게 하는 안전장치 PR**입니다.

---

# PR0 작업지시서 완성본

## 제목

**PR0: Analyzer에서 `source` 필드 제안 제거(테스트 그린화)**

---

## 1) 배경과 문제 정의

### 현재 테스트가 요구하는 동작

`tests/test_ticket_analysis_speed.py`의 첫 번째 테스트는 다음을 강제합니다:

* Analyzer 단계에서 반환되는 `analysis_result.field_proposals`에
  **`field_name == "source"` 인 제안이 최종적으로 남아 있으면 안 된다** 

테스트는 LLM 호출을 monkeypatch로 막고, fake 결과에 `source` 제안을 넣은 뒤, `analyze_ticket(state)` 결과에 `source`가 남아있는지 확인합니다. 

### 현재 코드 동작(원인)

`app/agents/analyzer.py`의 `analyze_ticket()`은:

* `fields_only` 여부에 따라 LLMAdapter 호출을 다르게 하고 
* `selected_fields`가 있을 때만 필터링을 수행합니다 

즉, `selected_fields`가 빈 배열이면(`[]`) **어떤 제안도 필터링되지 않아** `source`가 그대로 남습니다. 
→ 테스트가 깨지는 구조입니다.

---

## 2) PR0 목표(한 문장)

**Analyzer 결과의 `field_proposals`에서 `field_name == "source"` 항목은 항상 제거되도록 수정하여 `pytest -q`를 통과시킨다.**

---

## 3) 작업 범위

### 수정 대상 파일

* `app/agents/analyzer.py` 

### 참고/검증 대상 테스트

* `tests/test_ticket_analysis_speed.py::test_analyzer_filters_out_source_field_proposals` 

### 범위 밖(절대 하지 말 것)

* API 경로/스키마/스트리밍 변경 ❌
* LLM 로직 변경(프롬프트/모델/호출 방식) ❌
* 다른 최적화/리팩토링 섞기 ❌
  → PR0는 **버그픽스 1건만** 합니다.

---

## 4) 구현 요구사항(정확한 규칙)

### 필수 규칙

1. `analysis_result`에 `field_proposals`가 존재하면,
   그 리스트에서 `field_name == "source"` 인 항목은 **항상 제거**합니다.
2. 기존 `selected_fields` 필터 로직은 유지합니다. 
3. `selected_fields` 안에 `"source"`가 있더라도, **source는 제거**됩니다.
   (테스트가 “남지 않아야 한다”고 강제합니다) 
4. `analysis_result["field_proposals"]`가 없거나 None이면 안전하게 통과해야 합니다.

### 권장 구현 형태(가장 안전한 순서)

* (1) source 제거
* (2) selected_fields가 있으면 그 후 선택 필드만 남기기

예시 로직(개념):

```python
proposals = analysis_result.get("field_proposals") or []
proposals = [p for p in proposals if p.get("field_name") != "source"]

if selected_fields:
    proposals = [p for p in proposals if p.get("field_name") in selected_fields]

analysis_result["field_proposals"] = proposals
```

---

## 5) 작업 절차(개발자가 실제로 해야 할 순서)

1. 브랜치 생성

   * 예: `fix/pr0-filter-source-proposals`
2. 테스트 재현

   * `pytest -q` (또는 최소: `pytest -q tests/test_ticket_analysis_speed.py::test_analyzer_filters_out_source_field_proposals`)
3. 코드 수정 (`app/agents/analyzer.py`)
4. 테스트 통과 확인

   * `pytest -q`
5. 커밋

   * 커밋 메시지 추천: `fix: drop source field proposals in analyzer`
6. PR 생성

   * PR 제목 추천: `PR0: Filter out source field proposals in analyzer`
   * PR 설명에 “무엇을/왜/어떻게/테스트”를 짧게 포함

---

## 6) Copilot/Codex에 바로 붙여넣을 “작업지시 프롬프트”

아래는 그대로 복사해서 쓰시면 됩니다.

### 프롬프트(단일)

```text
작업: tests/test_ticket_analysis_speed.py::test_analyzer_filters_out_source_field_proposals 가 통과하도록 수정하세요.

배경:
- 테스트는 Analyzer 단계에서 analysis_result.field_proposals에 field_name=="source" 제안이 남으면 실패합니다.
- 현재 app/agents/analyzer.py는 selected_fields가 있을 때만 field_proposals를 필터링합니다.

수정 대상:
- app/agents/analyzer.py 의 analyze_ticket()

요구사항:
1) analysis_result에 field_proposals가 있으면, 그 목록에서 field_name=="source" 인 항목은 항상 제거하세요.
2) 기존 selected_fields 필터 로직은 유지하세요.
3) selected_fields 안에 "source"가 있어도 source는 제거되어야 합니다.
4) 다른 파일 변경 금지(이 PR은 버그픽스 1건만).

검증:
- pytest -q
- 최소한 tests/test_ticket_analysis_speed.py::test_analyzer_filters_out_source_field_proposals 통과

산출물:
- 변경 diff(요약)
- 왜 이 변경이 테스트를 만족하는지 2~3문장 설명
```

---

## 7) PR 리뷰 체크리스트(최소)

* [ ] `source`가 **항상 제거**되는지 (selected_fields 유무 관계없이) 
* [ ] 기존 `selected_fields` 동작이 유지되는지 
* [ ] 다른 동작 변화/리팩토링이 섞이지 않았는지
* [ ] `pytest -q` 통과

---

## 8) 리스크/롤백

* 리스크: 낮습니다. `field_proposals` 리스트에서 `source`만 제거하는 단순 필터입니다.
* 롤백: 이 커밋 1개 revert 하면 끝입니다.

---

## 9) PR0 완료 기준(Definition of Done)

* `pytest -q` 통과
* 특히 아래 테스트 통과:

  * `tests/test_ticket_analysis_speed.py::test_analyzer_filters_out_source_field_proposals` 
* 변경 파일은 `app/agents/analyzer.py` 1개(또는 동일 목적의 최소 변경)만 포함

---

원하시면, 다음 답변에서 **PR2(LLM Gateway) 작업지시서 완성본**을 “파일 트리 + 클래스/함수 시그니처 + 테스트 설계 + Copilot 프롬프트”까지 포함해서 바로 드리겠습니다.
