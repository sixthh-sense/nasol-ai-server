import os
import uuid

import requests
from datetime import datetime
from util.log.log import Log

logger = Log.get_logger()
class KftcService:
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


    @staticmethod
    def _get_env_var(key: str) -> str:
        # 환경변수를 읽고 None인 경우 예외를 발생
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Environment variable {key} is not set")
        return value

    @staticmethod
    def get_access_token(auth_code: str):
        url = "https://testapi.openbanking.or.kr/oauth/2.0/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": KftcService._get_env_var("KFTC_CLIENT_ID"),
            "client_secret": KftcService._get_env_var("KFTC_CLIENT_SECRET"),
            "code": auth_code,
            "redirect_uri": KftcService._get_env_var("KFTC_REDIRECT_URI")
        }
        logger.debug("[DEBUG] data fetched")
        resp = requests.post(url, data=data)
        return resp.json()  # access_token, refresh_token 등 포함

    # -----------------------------
    # 2) 사용자 정보 조회 (계좌 목록)
    # -----------------------------
    @staticmethod
    def get_user_info(access_token: str, user_seq_no: str):
        url = "https://testapi.openbanking.or.kr/v2.0/user/me"

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user_seq_no": user_seq_no}

        return requests.get(url, headers=headers, params=params).json()

    # -----------------------------
    # 계좌 거래 내역 조회
    # -----------------------------
    @staticmethod
    def generate_bank_tran_id():
        return f"M202300000U{uuid.uuid4().hex[:9]}"

    @staticmethod
    def get_account_transactions(access_token, bank_tran_id,
                                 fintech_use_num, from_date, to_date):

        url = "https://testapi.openbanking.or.kr/v2.0/account/transaction_list/fin_num"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "bank_tran_id": bank_tran_id,
            "fintech_use_num": fintech_use_num,
            "inquiry_type": "A",
            "inquiry_base": "D",
            "from_date": from_date,
            "to_date": to_date,
            "sort_order": "D",
            "tran_dtime": datetime.now().strftime("%Y%m%d%H%M%S")
        }

        return requests.post(url, data=payload, headers=headers).json()

    # -----------------------------
    # 3) 카드 목록 조회
    # -----------------------------
    @staticmethod
    def get_card_list(access_token: str, user_seq_no: str):
        url = "https://testapi.openbanking.or.kr/v2.0/user/card-info"

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user_seq_no": user_seq_no}

        return requests.get(url, headers=headers, params=params).json()

        # -----------------------------
        # 4) 카드 승인 내역 조회
        # -----------------------------

    @staticmethod
    def get_card_transactions(access_token, user_seq_no,
                              org_code, from_datetime, to_datetime):

        url = "https://testapi.openbanking.or.kr/v2.0/card/approval_list"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "user_seq_no": user_seq_no,
            "org_code": org_code,
            "from_date": from_datetime,
            "to_date": to_datetime,
            "tran_dtime": datetime.now().strftime("%Y%m%d%H%M%S"),
            "next_page": "0001"
        }

        return requests.post(url, json=payload, headers=headers).json()