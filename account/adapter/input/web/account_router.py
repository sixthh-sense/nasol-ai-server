from fastapi import APIRouter, HTTPException, Depends

from account.adapter.input.web.session_helper import get_current_user
from account.adapter.input.web.response.account_response import AccountResponse
from account.adapter.input.web.request.update_account_request import UpdateAccountRequest
from account.application.usecase.account_usecase import AccountUseCase

account_router = APIRouter()
usecase = AccountUseCase().get_instance()

@account_router.get("/{oauth_type}/{oauth_id}", response_model=AccountResponse)
def get_account_by_oauth_id(oauth_type: str, oauth_id: str):
    account = usecase.get_account_by_oauth_id(oauth_type, oauth_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountResponse(
        session_id=account.session_id,
        oauth_id=account.oauth_id,
        oauth_type=account.oauth_type,
        nickname=account.nickname,
        name=account.name,
        profile_image=account.profile_image,
        email=account.email,
        phone_number=account.phone_number,
        active_status=account.active_status,
        updated_at=account.updated_at,
        created_at=account.created_at,
        role_id=account.role_id
    )

@account_router.put("/{session_id}", response_model=AccountResponse)
async def update_account(
    update_req: UpdateAccountRequest,
    session_id: str,
):
    # 기존 계정 조회 (세션 ID로)
    existing_account = usecase.get_account_by_session_id(session_id)
    if not existing_account:
        raise HTTPException(status_code=404, detail="Account not found")

    # 변경할 필드만 반영
    updated_account = UpdateAccountRequest(
        session_id=session_id,
        oauth_id=update_req.oauth_id,
        oauth_type=update_req.oauth_type,
        nickname=update_req.nickname if update_req and update_req.nickname is not None else existing_account.nickname,
        profile_image=update_req.profile_image if update_req and update_req.profile_image is not None else existing_account.profile_image,
        phone_number=update_req.phone_number if update_req and update_req.phone_number is not None else existing_account.phone_number,
        automatic_analysis_cycle=update_req.automatic_analysis_cycle if update_req and update_req.automatic_analysis_cycle is not None else getattr(existing_account, "automatic_analysis_cycle", None),
        target_period=update_req.target_period if update_req and update_req.target_period is not None else getattr(existing_account, "target_period", None),
        target_amount=update_req.target_amount if update_req and update_req.target_amount is not None else getattr(existing_account, "target_amount", None),
    )
    await usecase.update_account(updated_account)

    updated_account = usecase.get_account_by_session_id(session_id)

    return AccountResponse(
        session_id=updated_account.session_id,
        oauth_id=updated_account.oauth_id,
        oauth_type=updated_account.oauth_type,
        nickname=updated_account.nickname,
        name=updated_account.name,
        profile_image=updated_account.profile_image,
        email=updated_account.email,
        phone_number=updated_account.phone_number,
        active_status=updated_account.active_status,
        updated_at=updated_account.updated_at,
        created_at=updated_account.created_at,
        role_id=updated_account.role_id,
        automatic_analysis_cycle=getattr(updated_account, "automatic_analysis_cycle", None),
        target_period=getattr(updated_account, "target_period", None),
        target_amount=getattr(updated_account, "target_amount", None),
    )

@account_router.delete("/{oauth_type}/{oauth_id}")
def delete_account_by_oauth_id(oauth_type: str, oauth_id: str):
    return usecase.delete_account_by_oauth_id(oauth_type, oauth_id)

@account_router.get("/me")
def get_account_by_session_id(session_id: str = Depends(get_current_user)):
    return usecase.get_account_by_session_id(session_id)