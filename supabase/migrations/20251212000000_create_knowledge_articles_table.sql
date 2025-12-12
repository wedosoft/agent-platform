-- ============================================
-- 온보딩 자료실 (Knowledge Articles) 테이블 생성
-- Date: 2025-12-12
-- Description: 온보딩 자료실에서 사용자가 작성한 지식 문서를 영구 저장
-- ============================================

-- knowledge_articles 테이블 생성
CREATE TABLE IF NOT EXISTS onboarding.knowledge_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 기본 정보
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,

    -- 콘텐츠
    raw_content TEXT NOT NULL,
    structured_summary TEXT,

    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_knowledge_articles_category
    ON onboarding.knowledge_articles(category);

CREATE INDEX IF NOT EXISTS idx_knowledge_articles_author
    ON onboarding.knowledge_articles(author);

CREATE INDEX IF NOT EXISTS idx_knowledge_articles_created_at
    ON onboarding.knowledge_articles(created_at DESC);

-- 전체 텍스트 검색 인덱스 (제목 + 원본 콘텐츠)
-- Note: 'simple' 사용 (한국어 형태소 분석기가 없는 경우)
CREATE INDEX IF NOT EXISTS idx_knowledge_articles_search
    ON onboarding.knowledge_articles
    USING gin(to_tsvector('simple', title || ' ' || raw_content));

-- 테이블 설명
COMMENT ON TABLE onboarding.knowledge_articles IS '온보딩 자료실 지식 문서 (인수인계, 프로세스, 팁 등)';
COMMENT ON COLUMN onboarding.knowledge_articles.category IS '문서 카테고리 (handover, process, tips, company, tools)';
COMMENT ON COLUMN onboarding.knowledge_articles.raw_content IS '사용자가 작성한 원본 콘텐츠';
COMMENT ON COLUMN onboarding.knowledge_articles.structured_summary IS 'AI로 구조화된 요약 (마크다운)';