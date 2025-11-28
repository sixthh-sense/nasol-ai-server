import secrets
from fastapi import Request, HTTPException

CSRF_COOKIE_NAME = "csrf_token"

# -----------------------
# 랜덤 CSRF 토큰 생성
# -----------------------
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# -----------------------
# 요청 헤더에서 CSRF 토큰 검증
# -----------------------
def verify_csrf_token(request: Request, csrf_token_from_header: str):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not csrf_token_from_header or cookie_token != csrf_token_from_header:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

