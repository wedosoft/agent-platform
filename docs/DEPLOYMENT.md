# Fly.io 배포 가이드

이 프로젝트는 GitHub Actions를 통해 Fly.io에 자동으로 배포됩니다.

## 사전 준비

### 1. Fly.io 계정 및 앱 생성

```bash
# Fly CLI 설치 (macOS)
brew install flyctl

# 로그인
flyctl auth login

# 앱 생성 (처음 한 번만)
flyctl apps create agent-platform --org personal
```

### 2. GitHub Secrets 설정

GitHub 리포지토리 → Settings → Secrets and variables → Actions에서 다음 secret을 추가하세요:

- `FLY_API_TOKEN`: Fly.io API 토큰
  ```bash
  # 토큰 생성
  flyctl auth token
  ```

### 3. 환경 변수 설정

Fly.io에 필요한 환경 변수를 설정합니다:

```bash
# Supabase 설정
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_URL=https://xxxx.supabase.co
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_SERVICE_ROLE_KEY=your-key
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_TABLE_NAME=documents
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_BATCH_SIZE=25
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_LANGUAGES=ko,en
flyctl secrets set AGENT_PLATFORM_SUPABASE_COMMON_DEFAULT_PRODUCT=SharedDocs

# Gemini API 설정
flyctl secrets set GEMINI_API_KEY=your-gemini-api-key
flyctl secrets set AGENT_PLATFORM_GEMINI_COMMON_STORE_NAME=your-store-name

# Pipeline 설정 (선택)
flyctl secrets set AGENT_PLATFORM_PIPELINE_BASE_URL=http://your-pipeline-url

# Freshdesk 설정 (선택)
flyctl secrets set AGENT_PLATFORM_FRESHDESK_DOMAIN=your-domain
flyctl secrets set AGENT_PLATFORM_FRESHDESK_API_KEY=your-api-key
```

### 4. Redis 애드온 추가 (선택)

다중 인스턴스 배포 시 세션 상태 공유를 위해 Redis를 추가할 수 있습니다:

```bash
flyctl redis create
# 생성된 Redis URL이 자동으로 REDIS_URL 환경 변수로 설정됩니다
# 또는 수동으로 설정:
flyctl secrets set AGENT_PLATFORM_REDIS_URL=redis://...
```

## 배포 방법

### 자동 배포

`main` 브랜치에 푸시하면 GitHub Actions가 자동으로 배포를 시작합니다:

```bash
git add .
git commit -m "Deploy to fly.io"
git push origin main
```

### 수동 배포

GitHub Actions UI에서 "Deploy to Fly.io" 워크플로우를 수동으로 실행할 수도 있습니다.

### 로컬에서 배포

```bash
flyctl deploy
```

## 배포 확인

```bash
# 앱 상태 확인
flyctl status

# 로그 확인
flyctl logs

# 앱 열기
flyctl open

# Health check
curl https://agent-platform.fly.dev/api/health
```

## 머신 설정

현재 설정:
- **사양**: shared-cpu-1x
- **CPU**: 1 vCPU
- **메모리**: 512MB
- **머신 수**: 최대 1개
- **리전**: nrt (도쿄)
- **Auto-stop**: 활성화 (트래픽 없을 시 자동 중지)
- **Auto-start**: 활성화 (요청 시 자동 시작)
- **min_machines_running**: 0 (비용 절감)

사양 변경이 필요한 경우 [fly.toml](../fly.toml) 파일을 수정하세요.

## 문제 해결

### 배포 실패 시

```bash
# 상세 로그 확인
flyctl logs

# 앱 재시작
flyctl apps restart agent-platform
```

### 환경 변수 확인

```bash
# 설정된 secrets 목록 확인
flyctl secrets list
```

### Health check 실패

앱이 `/api/health` 엔드포인트를 제공하는지 확인하세요. 로컬에서 테스트:

```bash
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/api/health
```

## 비용 최적화

현재 설정은 최소 비용으로 운영됩니다:
- **머신 수 제한**: 최대 1개 머신만 실행
- **Auto-stop/start**: 사용하지 않을 때 자동 중지하여 비용 절감
- **min_machines_running = 0**: 트래픽 없을 때 머신 중지

프로덕션 환경에서는 `min_machines_running`을 1로 설정하여 콜드 스타트를 방지할 수 있습니다.

### 머신 확장 제어

현재 설정은 1개의 머신만 사용하도록 되어 있습니다. Fly.io가 자동으로 머신을 추가로 생성하지 않도록 하려면:

```bash
# 앱의 최대 머신 수를 1로 제한
flyctl scale count 1 --max-per-region 1
```
