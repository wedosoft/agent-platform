"""Supabase 공통 문서를 Gemini File Search 새 스토어에 메타데이터와 함께 재업로드합니다.

실행 전 준비
- .env.local 에 Supabase/Gemini 키가 있어야 합니다.
- 새 스토어 ID를 --store-id 로 전달해야 합니다.

예시
    python scripts/reupload_with_metadata.py \\
        --store-id ragtenantfreshdeskdefaultco-20241121-meta \\
        --display-name "Freshdesk 공통문서 with metadata" \\
        --product Freshdesk \\
        --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Dict, List, Optional

import httpx
from dotenv import load_dotenv

from app.core.config import get_settings
from app.services.common_documents import (
    CommonDocumentCursor,
    CommonDocumentsService,
    _build_common_documents_service,
)

LOGGER = logging.getLogger("reupload_with_metadata")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

START_ENDPOINT = (
    "https://generativelanguage.googleapis.com/upload/v1beta/"
    "{store_id}:uploadToFileSearchStore"
)
CREATE_STORE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/fileSearchStores"
GET_STORE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/{name}"


def build_metadata(record: Dict, *, lang: str, default_doc_type: str = "article") -> List[Dict[str, str]]:
    """레코드에서 사용 가능한 메타데이터를 추출해 customMetadata 리스트로 반환."""
    pairs = []

    def add(key: str, value: Optional[str]) -> None:
        if value is None:
            return
        value = str(value).strip()
        if not value:
            return
        if len(pairs) >= 20:  # Gemini 제약
            return
        pairs.append({"key": key, "stringValue": value})

    add("product", record.get("product"))
    add("locale", lang)
    add("slug", record.get("slug"))
    add("full_path", record.get("full_path"))
    add("short_slug", record.get("short_slug"))
    add("doc_type", default_doc_type)
    add("category_id", record.get("category_id"))
    add("folder_id", record.get("folder_id"))
    add("published", record.get("published"))
    add("visibility", record.get("visibility"))
    add("updated_at", record.get("updated_at"))
    add("source", "supabase_common")
    # 태그/키워드는 문자열로 병합
    meta_keywords = record.get("meta_keywords")
    if isinstance(meta_keywords, list):
        add("keywords", ",".join(meta_keywords))
    else:
        add("keywords", meta_keywords)

    tags = record.get("tags")
    if isinstance(tags, list):
        add("tags", ",".join(tags))
    else:
        add("tags", tags)

    return pairs


def pick_content(record: Dict, lang: str) -> Optional[str]:
    """언어별 컨텐츠에서 업로드할 텍스트를 선택."""
    html_key = f"content_html_{lang}"
    text_key = f"content_text_{lang}"
    return record.get(html_key) or record.get(text_key)


async def ensure_store_exists(api_key: str, *, store_id: str, display_name: Optional[str]) -> str:
    """스토어가 존재하면 반환, 없으면 새로 생성하고 이름을 반환."""
    headers = {"x-goog-api-key": api_key}
    if store_id:
        name = store_id if store_id.startswith("fileSearchStores/") else f"fileSearchStores/{store_id}"
        get_url = GET_STORE_ENDPOINT.format(name=name)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(get_url, headers=headers)
            if resp.status_code == 200:
                LOGGER.info("기존 스토어 사용: %s", name)
                return name
            LOGGER.info("지정한 스토어(%s)가 없어 새로 생성합니다 (GET %s)", name, resp.status_code)

    # 원하는 ID를 직접 줄 수 없으므로 displayName 기반 자동 생성
    payload = {"displayName": display_name or store_id or "file-search-store"}
    create_headers = {**headers, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(CREATE_STORE_ENDPOINT, headers=create_headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"스토어 생성 실패 {resp.status_code}: {resp.text}")
        name = resp.json().get("name")
        if not name:
            raise RuntimeError("스토어 생성 응답에 name이 없습니다.")
        LOGGER.info("새 스토어 생성: %s (displayName=%s)", name, payload["displayName"])
        return name


async def upload_document(
    api_key: str,
    *,
    store_id: str,
    filename: str,
    content: str,
    metadata: List[Dict[str, str]],
    timeout: float,
    max_attempts: int,
) -> None:
    """단일 문서를 새 스토어로 업로드."""
    start_url = START_ENDPOINT.format(store_id=store_id)
    content_bytes = content.encode("utf-8")
    start_headers = {
        "x-goog-api-key": api_key,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(content_bytes)),
        "X-Goog-Upload-Header-Content-Type": "text/plain; charset=utf-8",
        "Content-Type": "application/json",
    }
    start_body = {
        "displayName": filename,
        "customMetadata": metadata,
        "mimeType": "text/plain",
    }
    last_error: Optional[Exception] = None
    for attempt in range(max(1, max_attempts)):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                start_resp = await client.post(start_url, headers=start_headers, json=start_body)
                if start_resp.status_code >= 400:
                    raise RuntimeError(
                        f"업로드 시작 실패 {start_resp.status_code}: {start_resp.text}"
                    )
                upload_url = start_resp.headers.get("X-Goog-Upload-URL")
                if not upload_url:
                    raise RuntimeError("업로드 URL을 받지 못했습니다.")

                upload_headers = {
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-Goog-Upload-Command": "upload, finalize",
                    "X-Goog-Upload-Protocol": "resumable",
                    "X-Goog-Upload-Offset": "0",
                }
                upload_resp = await client.post(upload_url, headers=upload_headers, content=content_bytes)
                if upload_resp.status_code >= 400:
                    raise RuntimeError(
                        f"업로드 실패 {upload_resp.status_code}: {upload_resp.text}"
                    )
            return
        except (httpx.TimeoutException, httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 >= max_attempts:
                raise
            wait_seconds = min(5.0, 1.0 + attempt)
            LOGGER.warning("업로드 실패 재시도 (%s/%s): %s", attempt + 1, max_attempts, exc)
            await asyncio.sleep(wait_seconds)
    if last_error:
        raise last_error


async def upload_with_semaphore(
    sem: asyncio.Semaphore,
    api_key: str,
    *,
    store_id: str,
    filename: str,
    content: str,
    metadata: List[Dict[str, str]],
    timeout: float,
    max_attempts: int,
) -> None:
    async with sem:
        await upload_document(
            api_key,
            store_id=store_id,
            filename=filename,
            content=content,
            metadata=metadata,
            timeout=timeout,
            max_attempts=max_attempts,
        )


async def wipe_store_documents(api_key: str, store_name: str) -> None:
    """스토어의 모든 문서를 삭제."""
    headers = {"x-goog-api-key": api_key}
    base = f"https://generativelanguage.googleapis.com/v1beta/{store_name}/documents"
    async with httpx.AsyncClient(timeout=30) as client:
        next_page = ""
        deleted = 0
        while True:
            url = base
            if next_page:
                url += f"?pageToken={next_page}"
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"문서 목록 조회 실패 {resp.status_code}: {resp.text}")
            data = resp.json()
            docs = data.get("documents", [])
            for doc in docs:
                name = doc.get("name")
                if not name:
                    continue
                del_url = f"https://generativelanguage.googleapis.com/v1beta/{name}?force=true"
                del_resp = await client.delete(del_url, headers=headers)
                if del_resp.status_code >= 400:
                    raise RuntimeError(f"문서 삭제 실패 {del_resp.status_code}: {del_resp.text}")
                deleted += 1
            next_page = data.get("nextPageToken")
            if not next_page:
                break
    LOGGER.info("스토어 문서 삭제 완료: %s개", deleted)


def parse_columns_arg(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    items = [item.strip() for item in value.split(",")]
    cleaned = [item for item in items if item]
    return cleaned or None


async def reupload(
    *,
    store_id: str,
    display_name: Optional[str],
    limit: Optional[int],
    product: Optional[str],
    dry_run: bool,
    create_if_missing: bool,
    wipe_first: bool,
    resume_updated_at: Optional[str],
    resume_id: Optional[str],
    concurrency: int,
    upload_timeout: float,
    upload_attempts: int,
    columns: Optional[List[str]] = None,
    skip_count: int = 0,
) -> Optional[CommonDocumentCursor]:
    load_dotenv(".env.local")
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 가 설정되어 있지 않습니다.")

    service: CommonDocumentsService = _build_common_documents_service()
    if not create_if_missing:
        # 존재 확인만: 없으면 예외
        headers = {"x-goog-api-key": api_key}
        name = store_id if store_id.startswith("fileSearchStores/") else f"fileSearchStores/{store_id}"
        url = GET_STORE_ENDPOINT.format(name=name)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"스토어가 없습니다: {name} (status {resp.status_code})")
        store_name = name
    else:
        store_name = await ensure_store_exists(api_key, store_id=store_id, display_name=display_name)

    if wipe_first:
        await wipe_store_documents(api_key, store_name)

    if skip_count < 0:
        raise ValueError("skip_count 는 0 이상이어야 합니다.")

    skipped = 0
    produced = 0
    stop_requested = False
    cursor: Optional[CommonDocumentCursor] = None
    if resume_updated_at and resume_id:
        cursor = CommonDocumentCursor(id=resume_id, updated_at=resume_updated_at)

    last_cursor: Optional[CommonDocumentCursor] = None
    sem = asyncio.Semaphore(max(1, concurrency))
    while True:
        batch = service.fetch_documents(
            limit=limit,
            product=product,
            cursor=cursor,
            columns=columns,
        )
        records = batch.records
        if not records:
            break
        cursor = batch.cursor
        if cursor:
            last_cursor = cursor
        tasks: List[asyncio.Task] = []
        for record in records:
            # 언어 우선순위: 설정된 언어 순서
            for lang in service.config.languages:
                content = pick_content(record, lang)
                if not content:
                    continue
                metadata = build_metadata(record, lang=lang)
                filename = record.get("slug") or record.get("title_ko") or f"doc-{record.get('id')}"
                if skipped < skip_count:
                    skipped += 1
                    break
                if limit and produced >= limit:
                    stop_requested = True
                    break
                if dry_run:
                    LOGGER.info("[dry-run] 업로드 예정: %s (%s) meta=%s", filename, lang, metadata)
                else:
                    task = asyncio.create_task(
                        upload_with_semaphore(
                            sem,
                            api_key,
                            store_id=store_name,
                            filename=f"{filename}-{lang}",
                            content=content,
                            metadata=metadata,
                            timeout=upload_timeout,
                            max_attempts=upload_attempts,
                        )
                    )
                    tasks.append(task)
                produced += 1
                break  # 언어 한 개만 업로드
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    raise r
        if stop_requested:
            break
        if not cursor:
            break
    LOGGER.info("총 업로드(또는 dry-run) 문서 수: %s", produced)
    if last_cursor:
        LOGGER.info(
            "다음 실행 시 이어서 업로드하려면 --resume-updated-at %s --resume-id %s 를 사용하세요",
            last_cursor.updated_at,
            last_cursor.id,
        )
    return last_cursor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini File Search 스토어 재업로드")
    parser.add_argument("--store-id", required=True, help="새 File Search Store ID")
    parser.add_argument("--display-name", help="스토어 표시 이름")
    parser.add_argument("--limit", type=int, help="가져올 문서 수 제한(테스트용)")
    parser.add_argument("--product", help="특정 product 만 업로드")
    parser.add_argument("--dry-run", action="store_true", help="실제 업로드 없이 로그만 출력")
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="스토어가 없을 때 자동 생성 (기본은 존재하지 않으면 실패)",
    )
    parser.add_argument(
        "--wipe-first",
        action="store_true",
        help="업로드 전에 스토어의 기존 문서를 모두 삭제",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="동시 업로드 개수(기본 4). 429가 나면 줄이세요.",
    )
    parser.add_argument(
        "--upload-timeout",
        type=float,
        default=120.0,
        help="단일 업로드 HTTP 타임아웃(초). 기본 120초.",
    )
    parser.add_argument(
        "--upload-attempts",
        type=int,
        default=5,
        help="업로드 재시도 횟수. 기본 5회.",
    )
    parser.add_argument(
        "--resume-updated-at",
        help="이어 업로드 시작할 updated_at (ISO). --resume-id와 함께 사용",
    )
    parser.add_argument(
        "--resume-id",
        help="이어 업로드 시작할 마지막 문서 id. --resume-updated-at과 함께 사용",
    )
    parser.add_argument(
        "--columns",
        help="Supabase에서 읽어올 컬럼을 콤마로 지정 (기본은 전체)",
    )
    parser.add_argument(
        "--skip-count",
        type=int,
        default=0,
        help="선행 문서 N건을 건너뛰고 업로드 (병렬 실행 시 사용)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    columns = parse_columns_arg(args.columns)
    asyncio.run(
        reupload(
            store_id=args.store_id,
            display_name=args.display_name,
            limit=args.limit,
            product=args.product,
            dry_run=args.dry_run,
            create_if_missing=args.create_if_missing,
            wipe_first=args.wipe_first,
            resume_updated_at=args.resume_updated_at,
            resume_id=args.resume_id,
            concurrency=args.concurrency,
            upload_timeout=args.upload_timeout,
            upload_attempts=args.upload_attempts,
            columns=columns,
            skip_count=args.skip_count,
        )
    )


if __name__ == "__main__":
    main()
