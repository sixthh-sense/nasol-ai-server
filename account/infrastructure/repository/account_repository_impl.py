from typing import Optional
from account.application.port.account_repository_port import AccountRepositoryPort
from account.domain.account import Account
from account.infrastructure.orm.account_orm import AccountORM
from config.database.session import get_db_session
from sqlalchemy.orm import Session
from sqlalchemy import and_


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

    async def save(self, account: Account) -> Account:
        orm_account = AccountORM(
            session_id=account.session_id,
            oauth_id=account.oauth_id,
            oauth_type=account.oauth_type,
            nickname=account.nickname,
            name=account.name,
            profile_image=account.profile_image,
            email=account.email,
            phone_number=account.phone_number,
            active_status=account.active_status,
            role_id=account.role_id,
            automatic_analysis_cycle=account.automatic_analysis_cycle,
            target_period=account.target_period,
            target_amount=account.target_amount
        )

        self.db.add(orm_account)
        self.db.commit()
        self.db.refresh(orm_account)

        account.created_at = orm_account.created_at
        account.updated_at = orm_account.updated_at
        return account

    def get_by_oauth_id(self, oauth_type: str, user_oauth_id: str) -> Optional[Account]:
        orm_account = self.db.query(AccountORM).filter(AccountORM.oauth_type == oauth_type,
                                                       AccountORM.oauth_id == user_oauth_id).first()
        if orm_account:
            account = Account(
                session_id=orm_account.session_id,
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

    def get_account_by_id(self, oauth_id: str) -> Optional[Account]:
        orm_account = self.db.query(AccountORM).filter(AccountORM.oauth_id == oauth_id).first()
        if orm_account:
            account = Account(
                session_id=orm_account.session_id,
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

    def delete_account_by_oauth_id(self, oauth_type: str, oauth_id: str) -> bool:
        deleted_count = self.db.query(AccountORM).filter(
            and_(
                AccountORM.oauth_type == oauth_type,
                AccountORM.oauth_id == oauth_id
            )
        ).delete(synchronize_session=False)

        self.db.commit()

        return deleted_count > 0