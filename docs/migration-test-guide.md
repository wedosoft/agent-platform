# Freshdesk Phase1 마이그레이션 테스트 가이드

## 개요

이 문서는 Freshdesk Phase1 온보딩 커리큘럼 마이그레이션 후 프론트엔드 UI 테스트 절차를 안내합니다.

## 사전 준비

1. **마이그레이션 실행 완료 확인**
   - 백업 마이그레이션 실행: `20260105000000_backup_freshdesk_modules.sql`
   - 삭제 마이그레이션 실행: `20260105000001_delete_old_freshdesk_modules.sql`
   - Python 스크립트 실행: `python scripts/migrate_freshdesk_phase1.py`
   - 검증 SQL 실행: `20260105000002_verify_freshdesk_phase1.sql`

2. **백엔드 서버 실행**
   ```bash
   cd agent-platform
   uvicorn app.main:app --reload --port 8000
   ```

3. **프론트엔드 서버 실행**
   ```bash
   cd onboarding
   npm run dev
   ```

## 테스트 시나리오

### 1. 모듈 목록 페이지 테스트

**경로**: `/curriculum/freshdesk` 또는 `/products/freshdesk/curriculum`

**확인 사항**:
- [ ] Freshdesk Phase1 모듈이 **4개**만 표시되는지 확인
- [ ] 기존 11개 모듈이 사라졌는지 확인
- [ ] 모듈 순서가 올바른지 확인 (1. Freshdesk 시작하기 → 2. 티켓의 이해와 생명주기 → 3. 팀 및 권한 설정 → 4. 기본 티켓 처리)
- [ ] 각 모듈의 제목, 설명, 예상 소요 시간이 올바르게 표시되는지 확인

**예상 결과**:
```
✅ Freshdesk 시작하기 (42분)
✅ 티켓의 이해와 생명주기 (48분)
✅ 팀 및 권한 설정 (48분)
✅ 기본 티켓 처리 (50분)
```

### 2. 모듈 학습 페이지 테스트

**경로**: `/curriculum/freshdesk/{module-slug}` 또는 `/products/freshdesk/modules/{module-id}`

**각 모듈별 확인 사항**:

#### 모듈 1: Freshdesk 시작하기
- [ ] 모듈 정보가 올바르게 표시되는지 확인
- [ ] 섹션 목록이 표시되는지 확인 (overview, concept, feature-guide, practice, knowledge-check 등)
- [ ] 각 섹션의 콘텐츠가 마크다운으로 올바르게 렌더링되는지 확인
- [ ] "자가 점검" 탭 클릭 시 퀴즈 3개가 로드되는지 확인
- [ ] 퀴즈 문제가 올바르게 표시되는지 확인 (문제, 선택지, 정답 제출 후 해설)

#### 모듈 2: 티켓의 이해와 생명주기
- [ ] 모듈 정보 및 섹션 콘텐츠 확인
- [ ] "자가 점검" 탭에서 퀴즈 3개가 로드되는지 확인
- [ ] 퀴즈 정답 제출 후 해설이 표시되는지 확인

#### 모듈 3: 팀 및 권한 설정
- [ ] 모듈 정보 및 섹션 콘텐츠 확인
- [ ] "자가 점검" 탭에서 퀴즈가 로드되지 않거나 AI 생성 폴백이 동작하는지 확인
  - (JSON에 객관식 퀴즈가 없으므로 `quiz_questions` 테이블에 데이터가 없을 수 있음)

#### 모듈 4: 기본 티켓 처리
- [ ] 모듈 정보 및 섹션 콘텐츠 확인
- [ ] "자가 점검" 탭에서 퀴즈가 로드되지 않거나 AI 생성 폴백이 동작하는지 확인

### 3. 퀴즈 기능 상세 테스트

**모듈 1 또는 2에서 테스트**:

1. **퀴즈 로드**
   - [ ] "자가 점검" 탭 클릭 시 퀴즈가 즉시 로드되는지 확인
   - [ ] 브라우저 개발자 도구 Network 탭에서 `/api/curriculum/modules/{module-id}/questions` 요청이 성공하는지 확인
   - [ ] 응답 데이터에 `choices`, `question`, `context` 필드가 포함되어 있는지 확인

2. **퀴즈 답변 제출**
   - [ ] 각 문제에 답변 선택 후 "제출" 버튼 클릭
   - [ ] 정답/오답 여부가 표시되는지 확인
   - [ ] 해설(explanation)이 표시되는지 확인
   - [ ] 학습 포인트(learning_point)가 표시되는지 확인

3. **퀴즈 결과**
   - [ ] 모든 문제를 제출한 후 결과 화면이 표시되는지 확인
   - [ ] 정답률이 올바르게 계산되는지 확인
   - [ ] "다시 학습하기" 버튼이 동작하는지 확인

### 4. AI 멘토 채팅 테스트

**각 모듈의 "AI 멘토" 탭에서 테스트**:

- [ ] 채팅 입력창이 표시되는지 확인
- [ ] 질문 입력 후 AI 응답이 스트리밍으로 표시되는지 확인
- [ ] 모듈 관련 질문에 대해 적절한 답변이 생성되는지 확인
- [ ] 추천 질문 버튼이 동작하는지 확인

### 5. 진행 상태 저장 테스트

- [ ] 모듈 학습 중 페이지를 새로고침해도 진행 상태가 유지되는지 확인
- [ ] 다른 모듈로 이동 후 다시 돌아와도 진행 상태가 유지되는지 확인
- [ ] 퀴즈 완료 후 진행률이 업데이트되는지 확인

## API 엔드포인트 직접 테스트

### 1. 모듈 목록 조회

```bash
curl http://localhost:8000/api/curriculum/products/freshdesk/modules
```

**예상 응답**:
- `target_product_id: "freshdesk"`인 모듈이 4개 반환
- 각 모듈에 `id`, `name_ko`, `slug`, `description`, `estimated_minutes` 포함

### 2. 모듈 상세 조회

```bash
# 모듈 ID는 실제 삽입된 UUID로 대체
curl http://localhost:8000/api/curriculum/modules/{module-id}
```

### 3. 모듈 섹션 콘텐츠 조회

```bash
curl http://localhost:8000/api/curriculum/modules/{module-id}/contents?level=basic
```

**예상 응답**:
- 모듈별로 7~8개의 섹션 반환
- 각 섹션에 `section_type`, `title_ko`, `content_md`, `display_order` 포함

### 4. 퀴즈 문제 조회

```bash
curl http://localhost:8000/api/curriculum/modules/{module-id}/questions
```

**예상 응답**:
- 모듈 1~2: 각 3개의 퀴즈 반환
- 모듈 3~4: 빈 배열 반환 (또는 AI 생성 퀴즈)

### 5. 퀴즈 제출

```bash
curl -X POST http://localhost:8000/api/curriculum/modules/{module-id}/quiz/submit \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session",
    "answers": [
      {"questionId": "...", "choiceId": "a"}
    ]
  }'
```

## 문제 해결

### 문제: 모듈이 4개가 아닌 11개로 표시됨

**원인**: 삭제 마이그레이션이 실행되지 않았거나 실패했을 수 있음

**해결**:
1. Supabase에서 직접 확인:
   ```sql
   SELECT COUNT(*) FROM onboarding.curriculum_modules WHERE target_product_id = 'freshdesk';
   ```
2. 삭제 마이그레이션 재실행

### 문제: 퀴즈가 로드되지 않음

**원인**: 
- `quiz_questions` 테이블에 데이터가 없음
- API 엔드포인트 오류

**해결**:
1. Supabase에서 확인:
   ```sql
   SELECT COUNT(*) FROM onboarding.quiz_questions qq
   JOIN onboarding.curriculum_modules cm ON qq.module_id = cm.id
   WHERE cm.target_product_id = 'freshdesk';
   ```
2. 브라우저 개발자 도구에서 API 응답 확인
3. 백엔드 로그 확인

### 문제: 섹션 콘텐츠가 표시되지 않음

**원인**: `module_contents` 테이블에 데이터가 없거나 섹션 타입 매핑 오류

**해결**:
1. Supabase에서 확인:
   ```sql
   SELECT mc.* FROM onboarding.module_contents mc
   JOIN onboarding.curriculum_modules cm ON mc.module_id = cm.id
   WHERE cm.target_product_id = 'freshdesk'
   ORDER BY cm.display_order, mc.display_order;
   ```
2. Python 스크립트 재실행 (dry-run 모드로 먼저 확인)

## 롤백 절차

마이그레이션에 문제가 발생한 경우:

1. **백업 테이블에서 복원**:
   ```sql
   -- quiz_questions 복원
   INSERT INTO onboarding.quiz_questions 
   SELECT * FROM quiz_questions_backup_20260105;
   
   -- module_contents 복원
   INSERT INTO onboarding.module_contents 
   SELECT * FROM module_contents_backup_20260105;
   
   -- curriculum_modules 복원
   INSERT INTO onboarding.curriculum_modules 
   SELECT * FROM curriculum_modules_backup_20260105;
   ```

2. **또는 Supabase 대시보드에서 백업 테이블 확인 후 수동 복원**

## 체크리스트

마이그레이션 완료 후 다음 항목을 모두 확인하세요:

- [ ] 백업 마이그레이션 실행 완료
- [ ] 삭제 마이그레이션 실행 완료
- [ ] Python 스크립트 실행 완료 (에러 없음)
- [ ] 검증 SQL 실행 완료 (모듈 4개, 섹션 28~32개 확인)
- [ ] 프론트엔드 모듈 목록 페이지에서 4개 모듈 표시 확인
- [ ] 각 모듈의 학습 페이지에서 섹션 콘텐츠 표시 확인
- [ ] 모듈 1~2의 퀴즈 기능 동작 확인
- [ ] AI 멘토 채팅 기능 동작 확인
- [ ] 진행 상태 저장 기능 동작 확인

