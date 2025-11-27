from fastapi import APIRouter, HTTPException, Depends, Request, Cookie
from fastapi.responses import JSONResponse

from account.adapter.input.web.session_helper import get_current_user
from account.adapter.input.web.response.account_response import AccountResponse
from account.adapter.input.web.request.update_account_request import UpdateAccountRequest
from account.application.usecase.account_usecase import AccountUseCase
from account.infrastructure.orm.account_orm import OAuthProvider
from config.redis_config import get_redis
from sosial_oauth.infrastructure.service.google_oauth2_service import GoogleOAuth2Service
from util.log.log import Log

account_router = APIRouter()
usecase = AccountUseCase().get_instance()
redis_client = get_redis()
logger = Log.get_logger()

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

@account_router.post("/departure")
async def departure(request: Request, session_id: str | None = Cookie(None)):
    logger.debug("Departure called")
    logger.debug("Request headers:", request.headers)

    if not session_id:
        logger.debug("No session_id received. Returning error")
        response = JSONResponse({"success": False, "message": "No session found"}, status_code=400)
        response.delete_cookie(key="session_id")
        return response

    # Redis 세션 확인
    exists = redis_client.exists(session_id)
    logger.debug("Redis session exists:", exists)

    if not exists:
        logger.debug("Session not found in Redis")
        response = JSONResponse({"success": False, "message": "Session not found"}, status_code=400)
        response.delete_cookie(key="session_id")
        return response

    # session_id로 계정 조회
    account = usecase.get_account_by_session_id(session_id)
    logger.debug("Account found")

    if not account:
        logger.debug("Account not found for session_id:", session_id)
        # 계정이 없어도 세션과 쿠키는 삭제
        redis_client.delete(session_id)
        response = JSONResponse({"success": False, "message": "Account not found"}, status_code=404)
        response.delete_cookie(key="session_id")
        return response

    # Google 계정인 경우에만 token revoke 실행
    logger.debug(f"Account oauth_type: '{account.oauth_type}'")
    logger.debug(f"OAuthProvider.GOOGLE: '{OAuthProvider.GOOGLE}'")

    if account.oauth_type == OAuthProvider.GOOGLE:
        logger.debug("Google account detected, attempting token revoke")
        access_token = redis_client.hget(session_id, "USER_TOKEN")
        logger.debug(f"[DEBUG] Access token from Redis (type: {type(access_token)})")

        if access_token:
            try:
                if isinstance(access_token, bytes):
                    access_token = access_token.decode("utf-8")
                    logger.debug("[DEBUG] Decoded access token")

                # GUEST 토큰이 아닌 경우에만 revoke 시도
                if access_token != "GUEST":
                    logger.debug("Calling GoogleOAuth2Service.revoke_token()...")
                    result = GoogleOAuth2Service.revoke_token(access_token)
                    logger.debug(f"Google token revoke result: {result}")
                    logger.debug("Google token revoked successfully")

                else:
                    logger.debug("Skipping token revoke for GUEST user")
            except Exception as e:
                # Token revoke 실패해도 계속 진행 (이미 만료됐을 수 있음)
                import traceback
                logger.debug(f"[ERROR] Failed to revoke Google token: {str(e)}")
                logger.debug(f"[ERROR] Traceback: {traceback.format_exc()}")
        else:
            logger.debug("No access token found in Redis for Google account")
            logger.debug(f"All Redis keys for session_id: {redis_client.hkeys(session_id)}")
    else:
        logger.debug("Non-Google account detected, skipping token revoke")

    # 계정 삭제 (향후 table이 account 외에 더 늘어날 경우 이쪽에 테이블 삭제 로직 추가)
    deleted = usecase.delete_account_by_oauth_id(account.oauth_type, account.oauth_id)
    logger.debug("Account deleted:", deleted)

    # Redis 세션 삭제
    delete_result = redis_client.delete(session_id)
    logger.debug("Redis delete result:", delete_result)
    logger.debug("Redis session exists after delete?", redis_client.exists(session_id))
    # 쿠키 삭제와 함께 응답 반환
    response = JSONResponse({"success": True, "message": "Account deleted successfully"})
    response.delete_cookie(key="session_id")
    logger.debug("Cookie deleted from response")
    return response