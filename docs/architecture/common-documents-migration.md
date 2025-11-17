# Common Documents Migration Plan

## 목표
- Supabase에 저장된 "공통 문서" 레코드를 FastAPI 백엔드에서 직접 조회·가공하여 Node 파이프라인 의존성을 제거.
- LangGraph 파이프라인 또는 향후 Gemini File Search 동기화에서 재사용할 수 있는 공통 Python 서비스 계층을 마련.

## 현재 Node 구현 요약
- `CommonDocumentsService`가 Supabase REST를 호출해 문서를 페이지네이션하며, `product` 필터와 `updated_at` 기반 커서를 지원.
- 문서 텍스트를 정규화하고 chunk로 분할하여 Gemini RAG 스토어에 업로드.
- `/pipeline/common-products` 엔드포인트에서 제품 목록을 제공.

## Python 설계 방향
1. **Config → Service**: 환경 변수를 `Settings`로 읽고 `CommonDocumentsConfig`에 매핑. Supabase 연결(URL, Service Role Key, table 등)을 중앙 집중.
2. **Repository 계층**: `CommonDocumentsService`가 Supabase Python SDK를 사용해 `fetch_documents`, `count_documents`, `list_products` 기능을 노출.
3. **텍스트 처리 유틸**: 콘텐츠 정규화, chunking, summary 생성을 헬퍼 함수로 분리하여 LangGraph 단계와 공유.
4. **의존성 주입**: FastAPI `Depends`를 통해 서비스 인스턴스를 주입하고, `/api/common-products` 등 기존 엔드포인트가 직접 사용하도록 점진 전환.
5. **테스트 전략**: Supabase SDK의 query builder를 모킹하고, chunking/정규화 로직은 순수 함수 테스트로 커버.

## 남은 과제
- fetch 동작과 Gemini 문서 변환 로직 구현 및 테스트.
- `/api/common-products` → Python 서비스 호출로 전환.
- LangGraph 파이프라인에서 사용할 chunk 변환기/요약기 설계.
