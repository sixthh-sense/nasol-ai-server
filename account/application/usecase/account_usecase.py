from typing import Optional

from account.domain.account import Account
from account.infrastructure.repository.account_repository_impl import AccountRepositoryImpl


class AccountUseCase:
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.__instance.account_repo = AccountRepositoryImpl.get_instance()
        return cls.__instance

    @classmethod
    def get_instance(cls):
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance

    async def create_account(self, session_id:str, oauth_id:str, oauth_type: str, nickname: str, name:str, profile_image:str, email:str, phone_number:str, active_status:str, role_id:str):
        account = Account(session_id=session_id, oauth_id=oauth_id, oauth_type=oauth_type, nickname=nickname, name=name, profile_image=profile_image, email=email, phone_number=phone_number, active_status=active_status, role_id=role_id)
        return await self.account_repo.save(account)
    
    async def update_account(
        self,
        session_id: str,
        oauth_id: Optional[str] = None,
        oauth_type: Optional[str] = None,
        nickname: Optional[str] = None,
        profile_image: Optional[str] = None,
        phone_number: Optional[str] = None,
        # 필요하면 추가 필드도 Optional 처리
    ) -> Account:
        # 기존 계정 조회
        existing_account = await self.account_repo.get_by_session_id(session_id)
        if existing_account is None:
            raise Exception("Account not found")

        # 기존 값과 업데이트 값 병합
        updated_account = Account(
            session_id=session_id,
            oauth_id=oauth_id if oauth_id is not None else existing_account.oauth_id,
            oauth_type=oauth_type if oauth_type is not None else existing_account.oauth_type,
            nickname=nickname if nickname is not None else existing_account.nickname,
            profile_image=profile_image if profile_image is not None else existing_account.profile_image,
            phone_number=phone_number if phone_number is not None else existing_account.phone_number,
            active_status=getattr(existing_account, "active_status", ""),
            role_id=getattr(existing_account, "role_id", ""),
            name=getattr(existing_account, "name", ""),
            automatic_analysis_cycle=getattr(existing_account, "automatic_analysis_cycle", 0),
            target_period=getattr(existing_account, "target_period", 0),
            target_amount=getattr(existing_account, "target_amount", 0),
            created_at=getattr(existing_account, "created_at", None),
            updated_at=getattr(existing_account, "updated_at", None),
        )
        return await self.account_repo.update(updated_account)

    def get_account_by_oauth_id(self, oauth_type:str, oauth_id: str) -> Optional[Account]:
        return self.account_repo.get_account_by_oauth_id(oauth_type, oauth_id)

    def get_account_by_session_id(self, session_id: str) -> Optional[Account]:
        return self.account_repo.get_account_by_session_id(session_id)

    def delete_account_by_oauth_id(self, oauth_type: str, oauth_id: str) -> bool:
        return self.account_repo.delete_account_by_oauth_id(oauth_type, oauth_id)