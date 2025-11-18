from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.common_documents import (
    CommonDocumentCursor,
    CommonDocumentCursorModel,
    CommonDocumentFetchResponse,
    CommonProductsResponse,
)
from app.services.common_documents import (
    CommonDocumentsError,
    CommonDocumentsService,
    get_common_documents_service,
)

router = APIRouter(tags=["common-documents"])


def _handle_error(exc: CommonDocumentsError) -> HTTPException:
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/common-products", response_model=CommonProductsResponse)
def get_common_products(service: CommonDocumentsService = Depends(get_common_documents_service)) -> CommonProductsResponse:
    try:
        products = service.list_products()
    except CommonDocumentsError as exc:
        raise _handle_error(exc)
    return CommonProductsResponse(products=products)


@router.get(
    "/common-documents",
    response_model=CommonDocumentFetchResponse,
    response_model_by_alias=True,
)
def fetch_common_documents(
    limit: int = Query(20, ge=1, le=500),
    product: Optional[str] = None,
    cursor_id: Optional[int] = Query(None, alias="cursorId"),
    cursor_updated_at: Optional[str] = Query(None, alias="cursorUpdatedAt"),
    updated_since: Optional[str] = Query(None, alias="updatedSince"),
    service: CommonDocumentsService = Depends(get_common_documents_service),
) -> CommonDocumentFetchResponse:
    cursor: Optional[CommonDocumentCursor] = None
    if cursor_id is not None and cursor_updated_at:
        cursor = CommonDocumentCursor(id=cursor_id, updated_at=cursor_updated_at)

    try:
        result = service.fetch_documents(
            limit=limit,
            product=product,
            cursor=cursor,
            updated_since=updated_since,
        )
    except CommonDocumentsError as exc:
        raise _handle_error(exc)

    return CommonDocumentFetchResponse(
        records=result.records,
        cursor=CommonDocumentCursorModel.from_dataclass(result.cursor)
        if result.cursor
        else None,
    )
