from pydantic import BaseModel
from typing import Dict, Optional

class InsertIncomeRequest(BaseModel):
    session_id: Optional[str] = None
    income_data: Dict[str, str]