from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.verification.dependencies import get_current_user, get_db
from app.verification.repositories import documents as documents_repo
from app.verification.schemas.document import DocumentOut, DocumentUploadRequest, DocumentUploadResponse
from app.verification.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse)
def initiate_upload(request: DocumentUploadRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return document_service.initiate_upload(db, request)


@router.post("/{document_id}/confirm")
def confirm_upload(document_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document_service.confirm_upload(db, document_id)
    return {"status": "PROCESSING"}


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    document = documents_repo.get_by_id(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document