-- ============================================
-- Migration: Create Curriculum & Quiz Tables
-- Date: 2025-12-03
-- Description: 신입사원 제품 교육 시스템 - 커리큘럼/퀴즈/진도 테이블
-- Naming Convention: curriculum_* (커리큘럼 도메인)
-- ============================================

-- Enable required extensions (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. curriculum_modules (학습 모듈)
-- ============================================
-- Freshservice Core 모듈: 티켓 관리, 서비스 카탈로그, SLA 관리 등
CREATE TABLE IF NOT EXISTS curriculum_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 제품 연결
    product TEXT NOT NULL DEFAULT 'freshservice',  -- freshservice, freshdesk, etc.
    
    -- 모듈 정보
    name_ko TEXT NOT NULL,                    -- 한국어 명칭 (예: '티켓 관리')
    name_en TEXT,                             -- 영어 명칭 (예: 'Ticket Management')
    slug TEXT NOT NULL,                       -- URL용 슬러그 (예: 'ticket-management')
    description TEXT,                         -- 모듈 설명
    icon TEXT,                                -- 아이콘 (예: 'ticket', 'catalog', 'clock')
    
    -- 학습 메타데이터
    estimated_minutes INT DEFAULT 30,         -- 예상 학습 시간 (분)
    display_order INT DEFAULT 0,              -- 표시 순서
    is_active BOOLEAN DEFAULT true,           -- 활성화 여부
    
    -- KB 카테고리 연결 (RAG 검색용)
    kb_category_id UUID REFERENCES kb_categories(id) ON DELETE SET NULL,
    kb_category_slug TEXT,                    -- kb_categories.slug 참조 (편의용)
    
    -- 선행 조건
    prerequisites UUID[] DEFAULT ARRAY[]::UUID[],  -- 선행 모듈 ID 배열
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(product, slug)
);

CREATE INDEX idx_curriculum_modules_product ON curriculum_modules(product);
CREATE INDEX idx_curriculum_modules_slug ON curriculum_modules(slug);
CREATE INDEX idx_curriculum_modules_active ON curriculum_modules(is_active) WHERE is_active = true;
CREATE INDEX idx_curriculum_modules_order ON curriculum_modules(product, display_order);

COMMENT ON TABLE curriculum_modules IS 'Product education curriculum modules (e.g., Freshservice Ticket Management)';

-- ============================================
-- 2. quiz_questions (퀴즈 문제 은행)
-- ============================================
-- 수동 검수된 문제를 저장하는 테이블
CREATE TABLE IF NOT EXISTS quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 모듈 연결
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    
    -- 문제 메타데이터
    difficulty TEXT NOT NULL CHECK (difficulty IN ('basic', 'advanced')),  -- 기초/심화
    question_order INT DEFAULT 0,             -- 문제 순서 (같은 난이도 내)
    
    -- 문제 내용
    question TEXT NOT NULL,                   -- 문제 텍스트
    context TEXT,                             -- 시나리오/배경 설명 (선택)
    
    -- 선택지 (JSONB 배열)
    -- 형식: [{"id": "a", "text": "선택지 내용"}, {"id": "b", "text": "..."}, ...]
    choices JSONB NOT NULL,
    
    -- 정답 및 해설
    correct_choice_id TEXT NOT NULL,          -- 정답 선택지 ID (예: "a", "b", "c", "d")
    explanation TEXT,                         -- 정답 해설
    
    -- KB 문서 연결 (학습 자료 참조)
    kb_document_id UUID,                      -- 관련 kb_documents.id
    reference_url TEXT,                       -- 참조 URL (선택)
    
    -- 상태
    is_active BOOLEAN DEFAULT true,           -- 활성화 여부
    reviewed_at TIMESTAMPTZ,                  -- 검수 완료 일시
    reviewed_by TEXT,                         -- 검수자
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quiz_questions_module ON quiz_questions(module_id);
CREATE INDEX idx_quiz_questions_difficulty ON quiz_questions(module_id, difficulty);
CREATE INDEX idx_quiz_questions_active ON quiz_questions(is_active) WHERE is_active = true;

COMMENT ON TABLE quiz_questions IS 'Manually reviewed quiz questions for curriculum modules';

-- ============================================
-- 3. quiz_attempts (퀴즈 시도 기록)
-- ============================================
-- 사용자의 퀴즈 응시 기록
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 사용자/세션 연결
    session_id TEXT NOT NULL,                 -- onboarding_sessions.session_id
    user_id UUID,                             -- 향후 사용자 테이블 연결용 (선택)
    
    -- 모듈/난이도
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('basic', 'advanced')),
    
    -- 결과
    score INT NOT NULL,                       -- 점수 (0-100)
    total_questions INT NOT NULL,             -- 총 문제 수
    correct_count INT NOT NULL,               -- 정답 수
    is_passed BOOLEAN NOT NULL,               -- 통과 여부 (80점 이상)
    
    -- 상세 응답 (JSONB 배열)
    -- 형식: [{"questionId": "uuid", "choiceId": "a", "isCorrect": true, "correctChoiceId": "a"}, ...]
    answers JSONB NOT NULL,
    
    -- 소요 시간
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    duration_seconds INT,                     -- 소요 시간 (초)
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quiz_attempts_session ON quiz_attempts(session_id);
CREATE INDEX idx_quiz_attempts_module ON quiz_attempts(module_id);
CREATE INDEX idx_quiz_attempts_user ON quiz_attempts(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_quiz_attempts_passed ON quiz_attempts(session_id, module_id, is_passed);

COMMENT ON TABLE quiz_attempts IS 'User quiz attempt records with scores and answers';

-- ============================================
-- 4. user_module_progress (사용자 모듈 진도)
-- ============================================
-- 사용자별 모듈 학습 진도 추적
CREATE TABLE IF NOT EXISTS user_module_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 사용자/세션 연결
    session_id TEXT NOT NULL,                 -- onboarding_sessions.session_id
    user_id UUID,                             -- 향후 사용자 테이블 연결용 (선택)
    
    -- 모듈 연결
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    
    -- 학습 상태
    status TEXT NOT NULL DEFAULT 'not_started' 
        CHECK (status IN ('not_started', 'learning', 'quiz_ready', 'completed')),
    
    -- 학습 진도
    learning_started_at TIMESTAMPTZ,          -- 학습 시작 시간
    learning_completed_at TIMESTAMPTZ,        -- 학습 완료 시간
    
    -- 퀴즈 결과 (기초)
    basic_quiz_score INT,                     -- 기초 퀴즈 점수
    basic_quiz_passed BOOLEAN DEFAULT false,
    basic_quiz_attempts INT DEFAULT 0,        -- 기초 퀴즈 시도 횟수
    
    -- 퀴즈 결과 (심화)
    advanced_quiz_score INT,                  -- 심화 퀴즈 점수
    advanced_quiz_passed BOOLEAN DEFAULT false,
    advanced_quiz_attempts INT DEFAULT 0,     -- 심화 퀴즈 시도 횟수
    
    -- 완료 정보
    completed_at TIMESTAMPTZ,                 -- 모듈 완료 시간 (기초+심화 모두 통과)
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(session_id, module_id)
);

CREATE INDEX idx_user_module_progress_session ON user_module_progress(session_id);
CREATE INDEX idx_user_module_progress_module ON user_module_progress(module_id);
CREATE INDEX idx_user_module_progress_status ON user_module_progress(session_id, status);
CREATE INDEX idx_user_module_progress_user ON user_module_progress(user_id) WHERE user_id IS NOT NULL;

COMMENT ON TABLE user_module_progress IS 'User learning progress per curriculum module';

-- ============================================
-- 5. Trigger: updated_at 자동 갱신
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- curriculum_modules
DROP TRIGGER IF EXISTS trigger_curriculum_modules_updated_at ON curriculum_modules;
CREATE TRIGGER trigger_curriculum_modules_updated_at
    BEFORE UPDATE ON curriculum_modules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- quiz_questions
DROP TRIGGER IF EXISTS trigger_quiz_questions_updated_at ON quiz_questions;
CREATE TRIGGER trigger_quiz_questions_updated_at
    BEFORE UPDATE ON quiz_questions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- user_module_progress
DROP TRIGGER IF EXISTS trigger_user_module_progress_updated_at ON user_module_progress;
CREATE TRIGGER trigger_user_module_progress_updated_at
    BEFORE UPDATE ON user_module_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 6. RLS (Row Level Security) - 향후 활성화용
-- ============================================
-- 현재는 RLS 비활성화 상태로 시작
-- ALTER TABLE curriculum_modules ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_module_progress ENABLE ROW LEVEL SECURITY;
