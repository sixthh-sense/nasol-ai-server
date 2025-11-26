import uuid
import json
from fastapi import HTTPException, Cookie
from sosial_oauth.adapter.input.web.google_oauth2_router import redis_client

# session_id가 없다면 (비 로그인 유저) 
# GUEST로 redis에 session 생성한다. 
# 있다면 session_id 반환
def get_current_user(session_id: str = Cookie(None)) -> str:

    print("[DEBUG] Session ID:", session_id)
    if not session_id:
        session_id = str(uuid.uuid4())
        redis_client.hset(
            session_id,
            "USER_TOKEN",
            "GUEST"
        )
        redis_client.expire(session_id, 24 * 60 * 60)
        return session_id

    user_data_bytes = redis_client.hgetall(session_id)
    if not user_data_bytes:
        print("[DEBUG] Redis value is None")
        raise HTTPException(status_code=401, detail="세션이 유효하지 않습니다.")

    # bytes -> str -> dict
    if isinstance(user_data_bytes, bytes):
        user_data_str = user_data_bytes.decode("utf-8")
    else:
        user_data_str = str(user_data_bytes)

    return session_id
