# Agent Platform 관리 대시보드 설계 문서

> **작성일**: 2025년 11월 22일  
> **작성자**: Agent Platform Team  
> **상태**: 설계 진행 중

---

## 1. 배경 및 목적

### 1.1 프로젝트 개요

**Agent Platform**은 여러 AI 에이전트들의 백본(backbone) 역할을 하는 FastAPI 기반 백엔드 시스템입니다. 현재 SK Bioscience IT 지원 에이전트를 시작으로, 향후 다양한 테넌트와 플랫폼에 배포될 에이전트들을 통합 관리할 필요성이 대두되었습니다.

### 1.2 해결해야 할 문제

1. **다중 플랫폼 배포**
   - Homepage (wedosoft.net/agents/*)
   - Slack App (워크스페이스 통합)
   - Freshdesk Widget (티켓 시스템 내장)
   - Gmail Plugin (개인별 설치)
   - 기타 향후 추가될 플랫폼

2. **테넌트별 관리**
   - SK Bioscience: Freshservice KB만 접근
   - Customer A: 특정 제품군만 접근
   - 각 테넌트별 독립적인 RAG Store 관리

3. **통합 모니터링 필요**
   - 플랫폼별 사용량 분석
   - API 호출 통계
   - Gemini 토큰 소비 현황
   - 응답 품질 메트릭

4. **운영 효율성**
   - RAG Store 문서 업로드/삭제
   - 배포 상태 모니터링
   - 에러 로그 추적
   - 권한 관리

---

## 2. 아키텍처 설계

### 2.1 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    다양한 배포 플랫폼                          │
├─────────────────────────────────────────────────────────────┤
│  www.wedosoft.net/agents/*  │  Slack App  │  Freshdesk      │
│  Gmail Plugin               │  기타 플랫폼 │  ...            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ HTTP/HTTPS
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              api.wedosoft.net (FastAPI Backend)             │
├─────────────────────────────────────────────────────────────┤
│  • POST /api/chat           - 에이전트 대화                  │
│  • GET  /api/admin/deployments - 배포 현황                  │
│  • GET  /api/admin/analytics   - 사용량 분석                │
│  • POST /api/admin/stores      - RAG Store 관리             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ 관리 요청
                   ▼
┌─────────────────────────────────────────────────────────────┐
│         admin.wedosoft.net (관리 대시보드)                   │
├─────────────────────────────────────────────────────────────┤
│  • /dashboard      - 전체 현황                               │
│  • /deployments    - 배포 관리                               │
│  • /tenants        - 테넌트 관리                             │
│  • /analytics      - 사용량 분석                             │
│  • /stores         - RAG Store 관리                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 호스팅 구조

#### Option A: Homepage 통합 (/admin 경로)
```
www.wedosoft.net (하나의 Next.js 앱)
├── /                    # 홈페이지
├── /agents/common       # 공개 에이전트
├── /agents/sk-bioscience # SK 에이전트
└── /admin               # 관리 대시보드 (같은 도메인)
    ├── /dashboard
    ├── /deployments
    └── ...
```

**장점:**
- ✅ 배포 단순 (하나의 Vercel 프로젝트)
- ✅ 같은 도메인, SSL 공유
- ✅ 컴포넌트 재사용 (shadcn/ui)
- ✅ Middleware로 `/admin` 접근 제어 가능

**단점:**
- ❌ 홈페이지와 관리 도구가 코드베이스 공유
- ❌ 관리자용 번들이 일반 사용자에게도 로드됨 (미미함)
- ❌ 확장성 제한적

#### Option B: 독립 대시보드 (별도 호스팅)
```
www.wedosoft.net        # Homepage (Next.js)
└── /agents/*           # 공개 에이전트만

admin.wedosoft.net      # Agent Admin (별도 Next.js 프로젝트)
└── /                   # 관리 대시보드 전용

api.wedosoft.net        # Agent Platform (FastAPI)
└── /api/*              # 백엔드 API
```

**장점:**
- ✅ 완전한 관심사 분리
- ✅ 독립적 배포 및 스케일링
- ✅ 보안 강화 (별도 도메인, IP 화이트리스트)
- ✅ 번들 최적화 (각 서비스별 최적 크기)

**단점:**
- ❌ 도메인/호스팅 비용 추가
- ❌ 배포 복잡도 증가
- ❌ 컴포넌트 중복 가능성

---

## 3. 설계 결정

### 3.1 최종 권장사항

**단계적 접근 (Phased Approach)**

#### Phase 1: Homepage 통합 (현재 규모)
- **선택**: Option A (Homepage에 `/admin` 추가)
- **이유**:
  - 현재 테넌트 1개 (SK Bioscience)
  - 빠른 구현 가능
  - 기존 인프라 활용

#### Phase 2: 독립 대시보드 (확장 시점)
- **전환 시점**:
  - 테넌트 10개 이상
  - 관리 대시보드 복잡도 증가
  - 보안 요구사항 강화 (VPN 필요 등)
- **선택**: Option B로 마이그레이션

### 3.2 판단 근거

| 기준 | Homepage 통합 | 독립 대시보드 | 선택 |
|------|--------------|-------------|------|
| **구현 속도** | ⭐⭐⭐ 빠름 | ⭐⭐ 보통 | Phase 1 |
| **배포 복잡도** | ⭐⭐⭐ 단순 | ⭐⭐ 복잡 | Phase 1 |
| **보안** | ⭐⭐ 보통 | ⭐⭐⭐ 강력 | Phase 2 |
| **확장성** | ⭐⭐ 제한적 | ⭐⭐⭐ 유연 | Phase 2 |
| **유지보수** | ⭐⭐ 보통 | ⭐⭐⭐ 독립적 | Phase 2 |
| **비용** | ⭐⭐⭐ 저렴 | ⭐⭐ 추가 | Phase 1 |

---

## 4. 구현 계획

### 4.1 Phase 1: Homepage 통합 (/admin)

#### 4.1.1 디렉토리 구조
```
homepage/
├── app/
│   ├── admin/                    # 🆕 관리 대시보드
│   │   ├── layout.tsx            # 관리자 전용 레이아웃
│   │   ├── page.tsx              # 대시보드 메인
│   │   ├── dashboard/
│   │   │   └── page.tsx          # 전체 현황
│   │   ├── deployments/
│   │   │   ├── page.tsx          # 배포 목록
│   │   │   └── [platform]/
│   │   │       └── page.tsx      # 플랫폼별 상세
│   │   ├── tenants/
│   │   │   ├── page.tsx          # 테넌트 목록
│   │   │   └── [id]/
│   │   │       ├── page.tsx      # 테넌트 상세
│   │   │       └── settings/
│   │   │           └── page.tsx  # 설정
│   │   ├── analytics/
│   │   │   └── page.tsx          # 사용량 분석
│   │   └── stores/
│   │       ├── page.tsx          # RAG Store 목록
│   │       └── [storeId]/
│   │           └── page.tsx      # Store 상세
│   └── agents/                   # 기존 에이전트 UI
│
├── components/
│   └── admin/                    # 🆕 관리자 컴포넌트
│       ├── deployment-card.tsx
│       ├── tenant-table.tsx
│       ├── usage-chart.tsx
│       └── store-uploader.tsx
│
└── middleware.ts                 # 🆕 /admin 접근 제어
```

#### 4.1.2 Backend API 추가 (agent-platform)
```python
# app/api/admin/deployments.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/admin/deployments", tags=["admin"])

@router.get("/")
async def list_deployments():
    """모든 플랫폼의 에이전트 배포 현황"""
    return {
        "deployments": [
            {
                "id": "homepage-public",
                "platform": "homepage",
                "tenant": "public",
                "endpoint": "https://wedosoft.net/agents/common",
                "status": "active",
                "last_request": "2025-11-22T10:30:00Z"
            },
            {
                "id": "slack-skbio",
                "platform": "slack",
                "tenant": "sk-bioscience",
                "workspace_id": "T01234567",
                "status": "active",
                "last_request": "2025-11-22T10:25:00Z"
            }
        ]
    }

@router.get("/analytics")
async def get_deployment_analytics(
    platform: str = None,
    tenant: str = None,
    date_from: str = None,
    date_to: str = None
):
    """배포별 사용량 통계"""
    # Supabase에서 sessions, messages 테이블 집계
    pass

# app/api/admin/tenants.py
@router.get("/")
async def list_tenants():
    """테넌트 목록"""
    pass

@router.get("/{tenant_id}")
async def get_tenant_detail(tenant_id: str):
    """테넌트 상세 정보 및 설정"""
    pass

# app/api/admin/stores.py
@router.get("/")
async def list_rag_stores():
    """RAG Store 목록"""
    pass

@router.post("/{store_id}/documents")
async def upload_documents(store_id: str, files: List[UploadFile]):
    """문서 업로드"""
    pass
```

#### 4.1.3 접근 제어 (Middleware)
```typescript
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // /admin 경로 보호
  if (request.nextUrl.pathname.startsWith('/admin')) {
    // 1. IP 화이트리스트 체크
    const ip = request.ip || request.headers.get('x-forwarded-for')
    const allowedIPs = process.env.ADMIN_ALLOWED_IPS?.split(',') || []
    
    if (!allowedIPs.includes(ip)) {
      return NextResponse.redirect(new URL('/403', request.url))
    }
    
    // 2. 인증 토큰 체크 (선택)
    const authToken = request.cookies.get('admin_token')
    if (!authToken) {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }
  
  return NextResponse.next()
}

export const config = {
  matcher: '/admin/:path*',
}
```

### 4.2 Phase 2: 독립 대시보드 마이그레이션

#### 4.2.1 새 프로젝트 생성
```bash
cd /Users/alan/GitHub
npx create-next-app@latest agent-admin \
  --typescript \
  --tailwind \
  --app \
  --src-dir

cd agent-admin
npx shadcn-ui@latest init

# 기본 컴포넌트 설치
npx shadcn-ui@latest add button card table chart
```

#### 4.2.2 환경 변수 설정
```bash
# agent-admin/.env.local
NEXT_PUBLIC_API_BASE_URL=https://api.wedosoft.net
NEXT_PUBLIC_ADMIN_API_KEY=admin_xxx

# IP 제한 (프로덕션)
ADMIN_ALLOWED_IPS=203.0.113.0,203.0.113.1

# 인증 (선택)
NEXTAUTH_URL=https://admin.wedosoft.net
NEXTAUTH_SECRET=xxx
```

#### 4.2.3 배포 설정
```yaml
# vercel.json (agent-admin)
{
  "env": {
    "NEXT_PUBLIC_API_BASE_URL": "@api-base-url"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        }
      ]
    }
  ]
}
```

---

## 5. 핵심 기능 정의

### 5.1 대시보드 (Dashboard)

**목적**: 전체 시스템 현황을 한눈에 파악

**주요 메트릭**:
- 총 활성 에이전트 수
- 24시간 API 호출 수
- 평균 응답 시간
- 에러율
- Gemini 토큰 소비량

**UI 구성**:
```typescript
// components/admin/dashboard-overview.tsx
export function DashboardOverview() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
      <MetricCard
        title="활성 에이전트"
        value={12}
        change="+2"
        changeType="increase"
      />
      <MetricCard
        title="24시간 API 호출"
        value="1,234"
        change="+15%"
        changeType="increase"
      />
      <MetricCard
        title="평균 응답 시간"
        value="1.2s"
        change="-0.3s"
        changeType="decrease"
      />
      <MetricCard
        title="에러율"
        value="0.5%"
        change="-0.2%"
        changeType="decrease"
      />
    </div>
  )
}
```

### 5.2 배포 관리 (Deployments)

**목적**: 여러 플랫폼에 배포된 에이전트 상태 모니터링

**플랫폼 유형**:
- `homepage`: wedosoft.net/agents/*
- `slack`: Slack 워크스페이스 앱
- `freshdesk`: Freshdesk 위젯
- `gmail`: Gmail 플러그인
- `custom`: 기타 커스텀 통합

**데이터 모델**:
```typescript
interface Deployment {
  id: string
  platform: 'homepage' | 'slack' | 'freshdesk' | 'gmail' | 'custom'
  tenant: string
  status: 'active' | 'inactive' | 'error'
  endpoint?: string
  workspace_id?: string // Slack
  subdomain?: string // Freshdesk
  config: Record<string, any>
  created_at: string
  last_request?: string
  metrics: {
    total_requests: number
    avg_response_time: number
    error_rate: number
  }
}
```

### 5.3 테넌트 관리 (Tenants)

**목적**: 고객사별 설정 및 권한 관리

**테넌트 속성**:
```typescript
interface Tenant {
  id: string
  name: string // "SK Bioscience"
  slug: string // "sk-bioscience"
  status: 'active' | 'inactive' | 'trial'
  plan: 'free' | 'basic' | 'enterprise'
  
  // RAG 설정
  rag_stores: string[] // ["fileSearchStores/freshworkskb..."]
  allowed_products: string[] // ["freshservice"]
  
  // 사용 제한
  quota: {
    max_api_calls_per_day: number
    max_tokens_per_month: number
  }
  
  // 현재 사용량
  usage: {
    api_calls_today: number
    tokens_this_month: number
  }
  
  // 배포 정보
  deployments: Deployment[]
  
  created_at: string
  updated_at: string
}
```

### 5.4 사용량 분석 (Analytics)

**목적**: 시간대별, 테넌트별 사용 패턴 분석

**차트 유형**:
1. **Timeline Chart**: 시간대별 API 호출
2. **Pie Chart**: 테넌트별 사용 비율
3. **Bar Chart**: 플랫폼별 비교
4. **Heatmap**: 요일/시간대별 패턴

**데이터 소스**:
```sql
-- Supabase Query 예시
SELECT 
  DATE_TRUNC('hour', created_at) as hour,
  tenant_id,
  COUNT(*) as request_count,
  AVG(response_time_ms) as avg_response_time
FROM sessions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY hour, tenant_id
ORDER BY hour DESC
```

### 5.5 RAG Store 관리 (Stores)

**목적**: 문서 업로드, 삭제, 스토어 성능 모니터링

**기능**:
- 문서 업로드 (PDF, DOCX, TXT)
- 문서 삭제
- 스토어 메타데이터 조회
- 검색 성능 테스트

**UI 예시**:
```typescript
// app/admin/stores/[storeId]/page.tsx
export default function StoreDetailPage({ params }) {
  return (
    <div>
      <StoreHeader store={store} />
      
      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">문서</TabsTrigger>
          <TabsTrigger value="upload">업로드</TabsTrigger>
          <TabsTrigger value="performance">성능</TabsTrigger>
        </TabsList>
        
        <TabsContent value="documents">
          <DocumentList storeId={params.storeId} />
        </TabsContent>
        
        <TabsContent value="upload">
          <DocumentUploader storeId={params.storeId} />
        </TabsContent>
        
        <TabsContent value="performance">
          <PerformanceMetrics storeId={params.storeId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

---

## 6. 보안 고려사항

### 6.1 인증 및 인가

**Option 1: IP 화이트리스트**
```typescript
// middleware.ts
const ALLOWED_IPS = [
  '203.0.113.0', // 사무실 IP
  '198.51.100.0', // VPN IP
]

if (!ALLOWED_IPS.includes(clientIP)) {
  return new Response('Forbidden', { status: 403 })
}
```

**Option 2: NextAuth.js**
```typescript
// app/api/auth/[...nextauth]/route.ts
import NextAuth from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

export const authOptions = {
  providers: [
    CredentialsProvider({
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // DB에서 관리자 계정 확인
        const user = await verifyAdmin(credentials)
        return user
      }
    })
  ]
}
```

### 6.2 API 키 관리

**Backend (agent-platform)**:
```python
# app/core/security.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-Admin-API-Key")

async def verify_admin_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

# app/api/admin/deployments.py
@router.get("/", dependencies=[Depends(verify_admin_api_key)])
async def list_deployments():
    pass
```

### 6.3 CORS 설정

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.wedosoft.net",
        "https://admin.wedosoft.net"  # Phase 2
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 7. 배포 전략

### 7.1 개발 환경

```bash
# Terminal 1: Backend
cd /Users/alan/GitHub/agent-platform
source venv/bin/activate
uvicorn app.main:app --port 8000 --reload

# Terminal 2: Homepage (with /admin)
cd /Users/alan/GitHub/homepage
npm run dev -- --port 3000

# Terminal 3: Admin Dashboard (Phase 2)
cd /Users/alan/GitHub/agent-admin
npm run dev -- --port 3001
```

### 7.2 프로덕션 배포

**Phase 1: Homepage 통합**
```
Vercel:
  - www.wedosoft.net (homepage + /admin)

Railway/Fly.io:
  - api.wedosoft.net (agent-platform)
```

**Phase 2: 독립 대시보드**
```
Vercel:
  - www.wedosoft.net (homepage only)
  - admin.wedosoft.net (agent-admin)

Railway/Fly.io:
  - api.wedosoft.net (agent-platform)
```

---

## 8. 마이그레이션 체크리스트

### 8.1 Phase 1 → Phase 2 전환 기준

- [ ] 테넌트 수 10개 이상
- [ ] 관리 대시보드 번들 크기 > 500KB
- [ ] 보안 요구사항 강화 (VPN 필수 등)
- [ ] 관리 기능 복잡도 증가
- [ ] 독립적 배포 필요성 대두

### 8.2 마이그레이션 절차

1. **agent-admin 프로젝트 생성**
   ```bash
   npx create-next-app@latest agent-admin
   ```

2. **Homepage에서 /admin 코드 복사**
   ```bash
   cp -r homepage/app/admin agent-admin/app/
   cp -r homepage/components/admin agent-admin/components/
   ```

3. **API 엔드포인트 변경**
   ```typescript
   // Before (Homepage)
   const API_BASE = '/api'
   
   // After (agent-admin)
   const API_BASE = 'https://api.wedosoft.net/api'
   ```

4. **Vercel 배포 설정**
   ```bash
   cd agent-admin
   vercel --prod
   # Domain: admin.wedosoft.net
   ```

5. **Homepage에서 /admin 제거**
   ```bash
   cd homepage
   rm -rf app/admin
   rm -rf components/admin
   ```

6. **DNS 설정**
   ```
   admin.wedosoft.net → Vercel (agent-admin)
   ```

---

## 9. 모니터링 및 운영

### 9.1 로깅

**Backend (agent-platform)**:
```python
# app/core/logging.py
import logging

logger = logging.getLogger("admin_api")
logger.setLevel(logging.INFO)

# app/api/admin/deployments.py
@router.get("/")
async def list_deployments():
    logger.info("Admin accessed deployment list", extra={
        "user_ip": request.client.host,
        "timestamp": datetime.utcnow()
    })
    return {...}
```

**Frontend (agent-admin)**:
```typescript
// lib/analytics.ts
export function trackAdminAction(action: string, metadata: any) {
  console.log('[Admin Action]', action, metadata)
  
  // 선택: External analytics
  // posthog.capture(action, metadata)
}

// Usage
trackAdminAction('deployment_viewed', { platform: 'slack' })
```

### 9.2 알림

**Slack Webhook 통합**:
```python
# app/services/notifications.py
import httpx

async def send_slack_alert(message: str):
    webhook_url = settings.slack_webhook_url
    await httpx.post(webhook_url, json={
        "text": f"🚨 Agent Platform Alert: {message}"
    })

# 사용 예시
if error_rate > 5:
    await send_slack_alert(f"Error rate exceeded: {error_rate}%")
```

---

## 10. 향후 확장 계획

### 10.1 추가 기능

1. **A/B 테스팅**
   - 프롬프트 버전 관리
   - 성능 비교 분석

2. **자동 스케일링**
   - 사용량 기반 RAG Store 용량 조정
   - API 레이트 리밋 동적 조정

3. **비용 최적화**
   - Gemini 토큰 사용량 예측
   - 비용 알림 설정

4. **멀티 리전 지원**
   - 글로벌 배포
   - 지역별 성능 모니터링

### 10.2 기술 스택 고려사항

**현재**:
- Frontend: Next.js + shadcn/ui
- Backend: FastAPI + Supabase
- AI: Gemini 2.0 Flash

**미래 검토 항목**:
- GraphQL (REST 대체)
- WebSocket (실시간 모니터링)
- Redis (캐싱)
- Prometheus + Grafana (메트릭)

---

## 11. 의사결정 요약

| 항목 | 결정 | 이유 |
|------|------|------|
| **초기 구조** | Homepage 통합 (/admin) | 빠른 구현, 기존 인프라 활용 |
| **확장 전략** | 단계적 분리 | 필요시 독립 대시보드로 마이그레이션 |
| **인증 방식** | IP 화이트리스트 + 선택적 NextAuth | 단순하면서 안전 |
| **Backend API** | FastAPI /admin/* 엔드포인트 | RESTful, 확장 용이 |
| **프론트엔드** | Next.js + shadcn/ui | Homepage와 일관성 |
| **배포** | Vercel (Frontend) + Railway (Backend) | 관리 편의성 |

---

## 12. 참고 자료

### 12.1 관련 문서
- [Agent Platform README](../README.md)
- [API Documentation](../API_REFERENCE.md)
- [Deployment Guide](../DEPLOYMENT.md)

### 12.2 외부 링크
- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Vercel Deployment](https://vercel.com/docs)

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 2025-11-22 | 1.0 | 초안 작성 | Agent Platform Team |

