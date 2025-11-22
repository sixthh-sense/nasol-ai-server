from fastapi import APIRouter, HTTPException

from account.application.usecase.account_usecase import AccountUseCase

account_router = APIRouter()
usecase = AccountUseCase().get_instance()

