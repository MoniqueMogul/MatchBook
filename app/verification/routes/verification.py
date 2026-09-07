from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.verification.dependencies import get_current_user, get_db
from app.verification.integrations import kyc_provider
from app.verification.services import verification_service
from app.verification.tasks.verification_tasks import start_business_verification_task, start_user_kyc_task

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post("/start")
async def start_verification(entity_type: str, entity_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if entity_type == "user":
        start_user_kyc_task(user_id=entity_id)
    elif entity_type == "business":
        start_business_verification_task(business_id=entity_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown entity_type: {entity_type}")
    return {"status": "PENDING"}


@router.get("/status")
def get_verification_status(entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    status = verification_service.get_status(db, entity_type, entity_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"entity_type": entity_type, "entity_id": entity_id, "status": status}


@router.post("/webhooks/didit")
async def didit_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Signature-V2", "")
    if not kyc_provider.verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = await request.json()
    result = kyc_provider.parse_webhook(payload)
    verification_service.handle_verification_result(db, result)
    return {"received": True}