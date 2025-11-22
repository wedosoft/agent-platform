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
) -> Dict[str, Any]:
    """스토어에 문서 업로드."""
    # 1. 업로드 시작
    start_url = f"{BASE_URL}/{store_name}:uploadToFileSearchStore"
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
    
    async with httpx.AsyncClient(timeout=60) as client:
        # 업로드 시작
        start_response = await client.post(start_url, headers=start_headers, json=start_body)
        start_response.raise_for_status()
        
        upload_url = start_response.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("업로드 URL을 받지 못했습니다.")
        
        # 파일 업로드
        upload_headers = {
            "Content-Length": str(len(file_content)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        
        upload_response = await client.put(upload_url, headers=upload_headers, content=file_content)
        upload_response.raise_for_status()
        
        result = upload_response.json()
        return {
            "name": result.get("name"),
            "displayName": result.get("displayName", file_name),
        }


async def delete_document(document_name: str) -> None:
    """개별 문서 삭제."""
    url = f"{BASE_URL}/{document_name}"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    params = {"force": "true"}
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(url, headers=headers, params=params)
        response.raise_for_status()
