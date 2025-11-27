from typing import Optional

from account.domain.account import Account
from account.infrastructure.repository.account_repository_impl import AccountRepositoryImpl
from account.adapter.input.web.request.update_account_request import UpdateAccountRequest
from util.log.log import Log

logger = Log.get_logger()
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
    
    def update_account(self, updated_account: UpdateAccountRequest):
        session_id = updated_account.session_id
        nickname = updated_account.nickname
        profile_image = updated_account.profile_image
        phone_number = updated_account.phone_number
        automatic_analysis_cycle = updated_account.automatic_analysis_cycle
        target_period = updated_account.target_period
        target_amount = updated_account.target_amount
        
        logger.info(f"nickname={nickname}")
        
        # 기존 계정 조회
        existing_account = self.account_repo.get_account_by_session_id(session_id)
        logger.info(f"existing_account={existing_account}")
        
        if existing_account is None:
            raise Exception("Account not found")

        # 기존 값과 업데이트 값 병합
        updated_account = Account.update(
            self,
            session_id=session_id if session_id is not None else existing_account.session_id,
            nickname=nickname if nickname is not None else existing_account.nickname,
            profile_image=profile_image if profile_image is not None else existing_account.profile_image,
            email=getattr(existing_account, "email", ""),
            phone_number=phone_number if phone_number is not None else existing_account.phone_number,
            active_status=getattr(existing_account, "active_status", ""),
            role_id=getattr(existing_account, "role_id", ""),
            automatic_analysis_cycle=automatic_analysis_cycle if automatic_analysis_cycle is not None else existing_account.automatic_analysis_cycle,
            target_period=target_period if target_period is not None else existing_account.target_period,
            target_amount=target_amount if target_amount is not None else existing_account.target_amount,
        )
        return self.account_repo.update(updated_account)

    def get_account_by_oauth_id(self, oauth_type:str, oauth_id: str) -> Optional[Account]:
        return self.account_repo.get_account_by_oauth_id(oauth_type, oauth_id)

    def get_account_by_session_id(self, session_id: str) -> Optional[Account]:
        return self.account_repo.get_account_by_session_id(session_id)

    def delete_account_by_oauth_id(self, oauth_type: str, oauth_id: str) -> bool:
        return self.account_repo.delete_account_by_oauth_id(oauth_type, oauth_id)