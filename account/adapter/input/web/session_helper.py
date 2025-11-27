import uuid
from fastapi import Cookie
from sosial_oauth.adapter.input.web.google_oauth2_router import redis_client
from util.log.log import Log

# session_id가 없다면 (비 로그인 유저) 
# GUEST로 redis에 session 생성한다. 
# 있다면 session_id 반환
logger = Log.get_logger()
def get_current_user(session_id: str = Cookie(None)) -> str:

    logger.debug("Session ID from cookie exists?: ", session_id is not None)
    # 1. 쿠키에 session_id가 없는 경우 → 새로 생성
    if not session_id:
        session_id = str(uuid.uuid4())
        redis_client.hset(
            session_id,
            "USER_TOKEN",
            "GUEST"
        )
        redis_client.expire(session_id, 24 * 60 * 60)
        logger.debug("Created new session_id")
        return session_id

    # 2. 쿠키에 session_id가 있는 경우 → Redis 확인
    user_data_bytes = redis_client.hgetall(session_id)
    logger.debug("Redis data for session_id is found")
    
    # 3. Redis에 데이터가 없는 경우 (만료되었거나 존재하지 않음)
    if not user_data_bytes:
        logger.debug("Session expired or not found, creating new one")
        # 에러 대신 새로운 session_id 생성
        new_session_id = str(uuid.uuid4())
        redis_client.hset(
            new_session_id,
            "USER_TOKEN",
            "GUEST"
        )
        redis_client.expire(new_session_id, 24 * 60 * 60)
        logger.debug("Created new session_id")
        return new_session_id

    # 4. Redis에 데이터가 있는 경우 → 기존 session_id 사용
    logger.debug("Using existing session_id")
    return session_id
