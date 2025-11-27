"""Google File Search API 서비스."""

import httpx
from typing import List, Optional, Dict, Any

from app.core.config import get_settings


settings = get_settings()
GEMINI_API_KEY = settings.gemini_api_key
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


async def get_file_search_stores() -> List[Dict[str, Any]]:
    """모든 File Search 스토어 목록 조회 (페이지네이션 처리)."""
    url = f"{BASE_URL}/fileSearchStores"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    
    all_stores = []
    next_page_token = None
    
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            params = {}
            if next_page_token:
                params["pageToken"] = next_page_token
            
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            stores = data.get("fileSearchStores", [])
            
            # 스토어 정보만 추가 (문서 수는 필요시에만 조회)
            for store in stores:
                all_stores.append({
                    "name": store["name"],
                    "displayName": store.get("displayName", store["name"]),
                    "documentCount": 0,  # 나중에 필요시 조회
                })
            
            # 다음 페이지가 있는지 확인
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
        
        return all_stores


async def create_file_search_store(display_name: str) -> Dict[str, Any]:
    """새 File Search 스토어 생성."""
    url = f"{BASE_URL}/fileSearchStores"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    body = {"displayName": display_name}
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        store = response.json()
        
        return {
            "name": store["name"],
            "displayName": store.get("displayName", display_name),
            "documentCount": 0,
        }


async def delete_file_search_store(store_name: str) -> None:
    """File Search 스토어 삭제."""
    # 먼저 문서 수 확인
    docs = await get_store_documents(store_name)
    if docs.get("documents") and len(docs["documents"]) > 0:
        raise ValueError("스토어에 문서가 있습니다. 먼저 모든 문서를 삭제하세요.")
    
    url = f"{BASE_URL}/{store_name}"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(url, headers=headers)
        response.raise_for_status()


async def get_store_documents(
    store_name: str, 
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """특정 스토어의 문서 목록 조회."""
    url = f"{BASE_URL}/{store_name}/documents"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    params = {}
    if page_token:
        params["pageToken"] = page_token
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        documents = []
        for doc in data.get("documents", []):
            metadata = []
            if "customMetadata" in doc:
                for meta in doc["customMetadata"]:
                    metadata.append({
                        "key": meta.get("key"),
                        "stringValue": meta.get("stringValue"),
                    })
            
            documents.append({
                "name": doc["name"],
                "displayName": doc.get("displayName", doc["name"]),
                "customMetadata": metadata if metadata else None,
            })
        
        return {
            "documents": documents,
            "nextPageToken": data.get("nextPageToken"),
        }


async def upload_document_to_store(
    store_name: str,
    file_name: str,
    file_content: bytes,
    metadata: Optional[List[Dict[str, str]]] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """스토어에 문서 업로드 (재시도 로직 포함)."""
    import asyncio
    
    # 업로드 전용 엔드포인트 사용 (BASE_URL이 아닌 upload 경로)
    upload_base_url = "https://generativelanguage.googleapis.com/upload/v1beta"
    start_url = f"{upload_base_url}/{store_name}:uploadToFileSearchStore"
    start_headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(file_content)),
        "X-Goog-Upload-Header-Content-Type": "text/plain; charset=utf-8",
        "Content-Type": "application/json",
    }
    
    start_body = {
        "displayName": file_name,
        "mimeType": "text/plain",
    }
    
    if metadata:
        start_body["customMetadata"] = [
            {"key": m.get("key"), "stringValue": m.get("value")}
            for m in metadata if m.get("key") and m.get("value")
        ]
    
    last_error = None
    for attempt in range(max_retries):
        try:
            # 대용량 파일 업로드를 위해 타임아웃을 5분으로 설정
            async with httpx.AsyncClient(timeout=300) as client:
                # 업로드 시작
                start_response = await client.post(start_url, headers=start_headers, json=start_body)
                
                # 에러 시 상세 내용 로깅
                if start_response.status_code >= 400:
                    error_detail = start_response.text
                    print(f"[ERROR] Upload start failed: {start_response.status_code}")
                    print(f"[ERROR] URL: {start_url}")
                    print(f"[ERROR] Request body: {start_body}")
                    print(f"[ERROR] Response: {error_detail}")
                    start_response.raise_for_status()
                
                # 헤더에서 업로드 URL 확인
                upload_url = start_response.headers.get("X-Goog-Upload-URL")
                if not upload_url:
                    raise RuntimeError("업로드 URL을 받지 못했습니다.")
                
                # 파일 업로드 (타임아웃 5분)
                upload_headers = {
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-Goog-Upload-Command": "upload, finalize",
                    "X-Goog-Upload-Protocol": "resumable",
                    "X-Goog-Upload-Offset": "0",
                }
                
                upload_response = await client.post(upload_url, headers=upload_headers, content=file_content)
                upload_response.raise_for_status()
                
                result = upload_response.json()
                return {
                    "name": result.get("name"),
                    "displayName": result.get("displayName", file_name),
                }
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2초, 4초, 6초
                print(f"[RETRY] Upload failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                print(f"[ERROR] Upload failed after {max_retries} attempts: {e}")
                raise last_error
    
    raise last_error or RuntimeError("Upload failed")


async def delete_document(document_name: str) -> None:
    """개별 문서 삭제."""
    url = f"{BASE_URL}/{document_name}"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    params = {"force": "true"}
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(url, headers=headers, params=params)
        response.raise_for_status()
