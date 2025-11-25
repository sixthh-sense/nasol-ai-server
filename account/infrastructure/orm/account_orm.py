from sqlalchemy import Column, String, DateTime, Enum as SAEnum, Integer
from enum import Enum as PyEnum
from datetime import datetime

from config.database.session import Base

class OAuthProvider(PyEnum):
    GOOGLE = "GOOGLE"
    NAVER = "NAVER"
    KAKAO = "KAKAO"

class YN(PyEnum):
    Y = "Y"
    N = "N"

class AccountORM(Base):
    __tablename__ = "account"

    session_id = Column(String(255), primary_key=True, nullable=False)
    oauth_id = Column(String(255), nullable=False)
    oauth_type = Column(SAEnum(OAuthProvider, native_enum=True), nullable=False, index=True)

    nickname = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    profile_image = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(255), nullable=True)
    active_status = Column(SAEnum(YN, native_enum=True), nullable=False, default=YN.Y)

    role_id = Column(String(255), nullable=True)    ## TODO 권한 관련 추가 후 nullable=False 작업 필요

    automatic_analysis_cycle = Column(Integer, nullable=True, default=0)
    target_period = Column(Integer, nullable=True, default=0)
    target_amount = Column(Integer, nullable=True, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AccountORM id={self.session_id} email={self.email} oauth_type={self.oauth_type} nickname={self.nickname}>"