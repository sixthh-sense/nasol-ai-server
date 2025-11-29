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
def verify_csrf_token(request: Request, csrf_token_from_header: str, required: bool = True):
    """
    CSRF 토큰 검증
    
    Args:
        request: FastAPI Request 객체
        csrf_token_from_header: 헤더에서 받은 CSRF 토큰
        required: True면 토큰 필수, False면 토큰이 없어도 허용 (비회원용)
    """
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    
    # required=False이고 둘 다 없으면 검증 통과 (비회원)
    if not required and not cookie_token and not csrf_token_from_header:
        return
    
    # 하나라도 있으면 둘 다 일치해야 함
    if not cookie_token or not csrf_token_from_header or cookie_token != csrf_token_from_header:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

