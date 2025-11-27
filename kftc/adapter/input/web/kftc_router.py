from fastapi import APIRouter

from kftc.infrastructure.service.kftc_service import KftcService
from util.log.log import Log

kftc_router = APIRouter()
svc = KftcService.get_instance()
logger = Log.get_logger()

@kftc_router.get("/redirect")
def auth_callback(code: str):
    token_data = svc.get_access_token(code)
    access_token = token_data["access_token"]
    user_seq_no = token_data["user_seq_no"]

    svc.access_token = access_token
    svc.user_seq_no = user_seq_no

    logger.debug("Access token fetched")

    # 2) 사용자 정보 조회 → 계좌 목록 포함
    user_info = svc.get_user_info(access_token, user_seq_no)
    logger.debug("User info fetched")

    # 3) 계좌 목록 기반 거래내역 조회
    account_results = []
    for acc in user_info.get("res_list", []):
        fintech_num = acc["fintech_use_num"]
        bank_tran_id = svc.generate_bank_tran_id()

        tx_list = svc.get_account_transactions(
            access_token=access_token,
            bank_tran_id=bank_tran_id,
            fintech_use_num=fintech_num,
            from_date="20251001",
            to_date="20251030"
        )

        account_results.append({
            "bank_name": acc["bank_name"],
            "account_num": acc["account_num_masked"],
            "transactions": tx_list
        })

    logger.debug("Account transactions fetched")

    # 4) 카드 목록 조회
    card_list = svc.get_card_list(access_token, user_seq_no)
    logger.debug("Card list fetched")

    # 5) 카드별 승인내역 조회
    card_results = []
    for card in card_list.get("card_list", []):
        org_code = card["org_code"]

        approval_list = svc.get_card_transactions(
            access_token=access_token,
            user_seq_no=user_seq_no,
            org_code=org_code,
            from_datetime="20240101",
            to_datetime="20240201"
        )

        card_results.append({
            "card_name": card["card_name"],
            "org_code": org_code,
            "approvals": approval_list
        })

    return {
        "user_info": user_info,
        "accounts": account_results,
        "cards": card_results
    }
