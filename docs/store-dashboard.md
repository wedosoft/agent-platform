## Google File Search 스토어 대시보드 초안

- 위치: `homepage` 리포 내 `docs/` 하위 폴더 추가 예정. 단순 정적 페이지 혹은 Next.js 기반 페이지 중 선택.
- 목적: 운영자가 Gemini File Search 스토어 상태를 한 화면에서 확인하고 정리할 수 있도록 함.

### 필수 기능
1. **스토어 목록 조회**
   - Supabase 혹은 Google File Search API에서 스토어 리스트를 불러와 테이블로 표시.
   - 각 스토어의 `displayName`, `store_id`, 문서 수, 최근 업데이트 시간 등을 노출.
2. **스토어 삭제**
   - 문서 수가 0인 스토어만 삭제 버튼 활성화.
   - 삭제 전 확인 모달에서 스토어 이름을 입력해야 실행되도록 함.
3. **저장된 문서 목록**
   - 선택한 스토어의 문서를 페이징으로 열람.
   - 기본 컬럼: `filename`, `locale`, `updated_at`, `size`, `customMetadata` 요약.
4. **문서 삭제**
   - 개별 삭제: 각 행에 삭제 아이콘 제공.
   - 일괄 삭제: 멀티 선택 후 `선택 삭제` 버튼. 진행 상황 표시 및 실패 건 리스트업.

### 기술 스택 제안
- 프론트: Next.js 14 / React Query / shadcn UI. 이미 homepage repo에서 사용 중인 스타일 재활용.
- 백엔드: 기존 FastAPI에 `/api/file-search` 계열 라우터 추가해 Google API 호출을 대행(키 노출 방지).
- 인증: 사내 Auth(예: Clerk) 연동 또는 Basic Auth.

### API 초안
| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/api/file-search/stores` | 스토어 리스트, 문서 수 포함. |
| DELETE | `/api/file-search/stores/{store_id}` | 문서 수 0일 때만 허용. |
| GET | `/api/file-search/stores/{store_id}/documents` | 문서 목록, `pageToken` 기반 페이징. |
| DELETE | `/api/file-search/documents/{doc_id}` | 개별 문서 삭제. |
| POST | `/api/file-search/documents/bulk-delete` | doc_id 배열 전달해 일괄 삭제. |

### UX 흐름
1. 페이지 진입 시 스토어 목록 로딩 → 빈 스토어만 삭제 버튼 활성화.
2. 특정 스토어 클릭 시 오른쪽 패널에서 문서 리스트 렌더링.
3. 문서 리스트에서 체크박스로 선택 후 일괄 삭제 가능, 또는 각 행의 휴지통 버튼으로 단일 삭제.
4. 모든 작업은 토스트로 성공/실패 피드백 제공.

### 체크리스트
- [ ] Google API 호출 시 서비스 계정 키를 서버에서만 사용.
- [ ] 문서 리스트 캐시를 두어 API quota 절약.
- [ ] 장기적으로 업로드 스크립트와 연동해 상태를 자동으로 갱신하도록 webhooks/cron 고려.

