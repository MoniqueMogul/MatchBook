from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.verification.dependencies import get_db
from app.verification.schemas.eligibility import EligibilityResult
from app.verification.schemas.financing import FinancingRequest, FinancingStatusOut
from app.verification.services import eligibility_service, financing_service

router = APIRouter(tags=["eligibility"])


@router.get("/eligibility", response_model=EligibilityResult)
def get_eligibility(buyer_id: UUID, business_id: UUID, current_user: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return eligibility_service.calculate_eligibility(db, buyer_id, business_id)


@router.post("/financing", response_model=FinancingStatusOut)
async def request_financing(request: FinancingRequest, current_user: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await financing_service.request_financing(db, request)


@router.get("/financing/{buyer_id}", response_model=FinancingStatusOut)
async def get_financing(buyer_id: UUID, current_user: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await financing_service.get_financing_status(db, buyer_id)