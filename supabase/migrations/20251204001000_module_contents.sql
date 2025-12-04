-- ============================================
-- 모듈 학습 콘텐츠 테이블
-- 정적 콘텐츠를 DB에 저장하여 LLM 지연 제거
-- ============================================

-- 기존 테이블 삭제 (있는 경우)
DROP TABLE IF EXISTS module_contents CASCADE;

-- 모듈 콘텐츠 테이블 생성
CREATE TABLE module_contents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    
    -- 섹션 타입: overview, core_concepts, features, practice, advanced, faq
    section_type VARCHAR(50) NOT NULL,
    
    -- 난이도: basic, intermediate, advanced
    level VARCHAR(20) NOT NULL DEFAULT 'basic',
    
    -- 섹션 제목 (UI 표시용)
    title_ko VARCHAR(200) NOT NULL,
    title_en VARCHAR(200),
    
    -- 콘텐츠 (마크다운)
    content_md TEXT NOT NULL,
    
    -- 표시 순서
    display_order INT NOT NULL DEFAULT 0,
    
    -- 메타데이터
    estimated_minutes INT DEFAULT 5,
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 유니크 제약: 모듈별 섹션+레벨 조합은 유일
    UNIQUE(module_id, section_type, level)
);

-- 인덱스
CREATE INDEX idx_module_contents_module ON module_contents(module_id);
CREATE INDEX idx_module_contents_level ON module_contents(level);
CREATE INDEX idx_module_contents_order ON module_contents(module_id, display_order);

-- 코멘트
COMMENT ON TABLE module_contents IS '모듈별 학습 콘텐츠 (기초/중급/고급)';
COMMENT ON COLUMN module_contents.section_type IS '섹션 타입: overview, core_concepts, features, practice, advanced, faq';
COMMENT ON COLUMN module_contents.level IS '난이도: basic, intermediate, advanced';
COMMENT ON COLUMN module_contents.content_md IS '마크다운 형식 콘텐츠';
