import uuid
import httpx

from fastapi import APIRouter, Request, Cookie, Header
from fastapi.responses import RedirectResponse, JSONResponse

from config.redis_config import get_redis
from sosial_oauth.application.usecase.google_oauth2_usecase import GoogleOAuth2UseCase
from sosial_oauth.infrastructure.service.google_oauth2_service import GoogleOAuth2Service
from utils.crsf import generate_csrf_token, verify_csrf_token, CSRF_COOKIE_NAME

# Singleton 방식으로 변경
authentication_router = APIRouter()
usecase = GoogleOAuth2UseCase().get_instance()
redis_client = get_redis()

@authentication_router.get("/google")
async def redirect_to_google():
    url = usecase.get_authorization_url()
    print("[DEBUG] Redirecting to Google:", url)
    return RedirectResponse(url)

@authentication_router.post("/logout")
async def logout_to_google(request: Request, session_id: str | None = Cookie(None), x_csrf_token: str | None = Header(None)):

    print("[DEBUG] Logout called")

    print("[DEBUG] Request headers:", request.headers)

    # CSRF 검증
    verify_csrf_token(request, x_csrf_token)

    if not session_id:
        print("[DEBUG] No session_id received. Returning logged_in: False")
        response = JSONResponse({"logged_in": False})
        response.delete_cookie(key="session_id")
        return response

    exists = redis_client.exists(session_id)
    print("[DEBUG] Redis has session_id?", exists)

    if exists:
        redis_client.delete(session_id)
        print("[DEBUG] Redis session_id deleted:", redis_client.exists(session_id))

    print("[DEBUG] TEST : ", redis_client.exists(session_id))

    # 쿠키 삭제와 함께 응답 반환
    response = JSONResponse({"logged_out": bool(exists)})
    response.delete_cookie(key="session_id")
    print("[DEBUG] Cookie deleted from response")
    return response

@authentication_router.get("/google/redirect")
async def process_google_redirect(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None
):
    # Google OAuth 에러 처리 (access_denied 등)
    if error:
        print(f"[DEBUG] Google OAuth error: {error}")
        return RedirectResponse("http://localhost:3000")
    print("[DEBUG] /google/redirect called")

    # session_id 생성
    session_id = str(uuid.uuid4())
    print("[DEBUG] Generated session_id:", session_id)

    # code -> access token
    access_token, session_id = await usecase.login_and_fetch_user(state or "", code, session_id)

    print("[[[[DEBUG]]]] ACCESS_TOKEN ", access_token)
    print(session_id)
    r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": access_token.access_token})
    print(r.status_code, r.text)

    # Redis에 session 저장 (1시간 TTL)
    redis_client.hset(
        session_id,
        "USER_TOKEN",
        access_token.access_token,
    )
    redis_client.expire(session_id, 24 * 60 * 60)
    print("[DEBUG] Session saved in Redis:", redis_client.exists(session_id))

    # CSRF 토큰 생성
    csrf_token = generate_csrf_token()
    print("[DEBUG] csrf_token:", csrf_token)

    # 브라우저 쿠키 발급
    response = RedirectResponse("http://localhost:3000")
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,           #배포 시 (https이용 시) True로 변경
        samesite="lax",         #배포 시 strict로 변경 (CSRF 대응)
        max_age=3600
    )

    # CSRF 토큰 쿠키 발급
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # JS에서 읽어서 헤더에 넣을 수 있도록 False
        secure=True,
        samesite="strict",
        max_age=3600
    )

    print("[DEBUG] Cookie set in RedirectResponse directly")
    return response



@authentication_router.get("/status")
async def auth_status(request: Request, session_id: str | None = Cookie(None)):
    print("[DEBUG] /status called")

    # 모든 요청 헤더 출력
    print("[DEBUG] Request headers:", request.headers)

    # 쿠키 확인
    print("[DEBUG] Received session_id cookie:", session_id)

    if not session_id:
        print("[DEBUG] No session_id received. Returning logged_in: False")
        return {"logged_in": False}

    exists = redis_client.exists(session_id)
    print("[DEBUG] Redis has session_id?", exists)

    return {"logged_in": bool(exists)}
