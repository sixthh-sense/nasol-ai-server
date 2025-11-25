from datetime import datetime

class Account:
    def __init__(self, session_id: str, oauth_id:str, oauth_type: str, nickname: str, name:str, profile_image:str, email:str, phone_number:str, active_status:str, role_id:str):
        self.session_id = session_id
        self.oauth_id = oauth_id
        self.oauth_type = oauth_type
        self.nickname = nickname
        self.name = name
        self.profile_image = profile_image
        self.email = email
        self.phone_number = phone_number
        self.active_status = active_status
        self.role_id = role_id
        self.automatic_analysis_cycle = 0
        self.target_period = 0
        self.target_amount = 0
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()

    def update(self, session_id: str, nickname: str, profile_image:str, email:str, phone_number:str, active_status:str, role_id:str, automatic_analysis_cycle:int, target_period: int, target_amount: int):
        self.session_id = session_id
        self.nickname = nickname
        self.profile_image = profile_image
        self.email = email
        self.phone_number = phone_number
        self.active_status = active_status
        self.role_id = role_id
        self.automatic_analysis_cycle = automatic_analysis_cycle
        self.target_period = target_period
        self.target_amount = target_amount
        return self