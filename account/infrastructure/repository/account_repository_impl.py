from typing import Optional

from account.application.port.account_repository_port import AccountRepositoryPort
from account.domain.account import Account
from account.infrastructure.orm.account_orm import AccountORM
from config.database.session import get_db_session
from sqlalchemy.orm import Session


class AccountRepositoryImpl(AccountRepositoryPort):
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    @classmethod
    def get_instance(cls):
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if not hasattr(self, 'db'):
            self.db: Session = get_db_session()

    def get_account_by_id(self, oauth_id: str) -> Optional[Account]:
        orm_account = self.db.query(AccountORM).filter(AccountORM.oauth_id == oauth_id).first()
        if orm_account:
            account = Account(
                oauth_id=orm_account.oauth_id,
                oauth_type=orm_account.oauth_type,
                nickname=orm_account.nickname,
                name=orm_account.name,
                profile_image=orm_account.profile_image,
                email=orm_account.email,
                phone_number=orm_account.phone_number,
                active_status=orm_account.active_status,
                role_id=orm_account.role_id
            )
            account.created_at = orm_account.created_at
            account.updated_at = orm_account.updated_at
            return account
        return None