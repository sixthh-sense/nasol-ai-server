from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UpdateAccountRequest(BaseModel):
    session_id: Optional[str] = None
    oauth_id: Optional[str] = None
    oauth_type: Optional[str] = None
    nickname: Optional[str] = None
    profile_image: Optional[str] = None
    phone_number: Optional[str] = None
    automatic_analysis_cycle: Optional[int] = None
    target_period: Optional[int] = None
    target_amount: Optional[int] = None