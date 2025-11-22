"""Google File Search 스토어 및 문서 관리 API."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.services.gemini_file_search import (
    create_file_search_store,
    delete_file_search_store,
    get_file_search_stores,
    get_store_documents,
    upload_document_to_store,
    delete_document,
)

router = APIRouter(prefix="/file-search", tags=["file-search"])


class StoreCreateRequest(BaseModel):
    """스토어 생성 요청."""
    displayName: str


class StoreResponse(BaseModel):
    """스토어 응답."""
    name: str
    displayName: str
    documentCount: Optional[int] = 0


class StoresListResponse(BaseModel):
    """스토어 목록 응답."""
    stores: List[StoreResponse]


class DocumentMetadata(BaseModel):
    """문서 메타데이터."""
    key: Optional[str] = None
    stringValue: Optional[str] = None


class DocumentResponse(BaseModel):
    """문서 응답."""
    name: str
    displayName: str
    customMetadata: Optional[List[DocumentMetadata]] = None


class DocumentsListResponse(BaseModel):
    """문서 목록 응답."""
    documents: List[DocumentResponse]
    nextPageToken: Optional[str] = None


@router.get("/stores", response_model=StoresListResponse)
async def list_stores():
    """모든 File Search 스토어 목록 조회."""
    try:
        stores = await get_file_search_stores()
        return StoresListResponse(stores=stores)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores", response_model=StoreResponse)
async def create_store(request: StoreCreateRequest):
    """새 File Search 스토어 생성."""
    try:
        store = await create_file_search_store(request.displayName)
        return store
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stores/{store_name:path}")
async def delete_store(store_name: str):
    """File Search 스토어 삭제 (문서 수 0일 때만)."""
    try:
        await delete_file_search_store(store_name)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/{store_name:path}/documents", response_model=DocumentsListResponse)
async def list_documents(store_name: str, pageToken: Optional[str] = None):
    """특정 스토어의 문서 목록 조회."""
    try:
        result = await get_store_documents(store_name, pageToken)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stores/{store_name:path}/documents")
async def upload_document(
    store_name: str,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    """스토어에 문서 업로드."""
    try:
        import json
        
        parsed_metadata = []
        if metadata:
            parsed_metadata = json.loads(metadata)
        
        file_content = await file.read()
        result = await upload_document_to_store(
            store_name=store_name,
            file_name=file.filename or "document.txt",
            file_content=file_content,
            metadata=parsed_metadata,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_name:path}")
async def delete_doc(document_name: str):
    """개별 문서 삭제."""
    try:
        await delete_document(document_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
