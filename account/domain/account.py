from datetime import datetime

class Account:
    def __init__(self, oauth_id:str, oauth_type: str, nickname: str, name:str, profile_image:str, email:str, phone_number:str, active_status:str, role_id:str):
        self.oauth_id = oauth_id
        self.oauth_type = oauth_type
        self.nickname = nickname
        self.name = name
        self.profile_image = profile_image
        self.email = email
        self.phone_number = phone_number
        self.active_status = active_status
        self.role_id = role_id
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()

    def update(self, nickname: str, profile_image:str, email:str, phone_number:str, active_status:str, role_id:str):
        self.nickname = nickname
        self.profile_image = profile_image
        self.email = email
        self.phone_number = phone_number
        self.active_status = active_status
        self.role_id = role_id
        return self