from account.adapter.input.web.request.create_account_request import CreateAccountRequest
from account.application.usecase.account_usecase import AccountUseCase
from sosial_oauth.adapter.input.web.request.get_access_token_request import GetAccessTokenRequest
from sosial_oauth.adapter.input.web.response.access_token import AccessToken
from sosial_oauth.infrastructure.service.google_oauth2_service import GoogleOAuth2Service

account_usecase = AccountUseCase().get_instance()

class GoogleOAuth2UseCase:
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
    def get_authorization_url() -> str:
        return GoogleOAuth2Service.get_authorization_url()

    async def login_and_fetch_user(self, state: str, code: str, session_id: str) -> AccessToken:
        try:
            # 1. Access token 획득
            access_token = self._fetch_access_token(state, code)

            # 2. 사용자 프로필 조회
            user_profile = self._fetch_user_profile(access_token)

            # 3. 계정 생성 또는 업데이트
            await self._create_or_update_account(user_profile, session_id)

            return access_token
        except Exception as e:
            raise Exception(f"Failed to login and fetch user: {str(e)}") from e

    @staticmethod
    def _fetch_access_token(state: str, code: str) -> AccessToken:
        # OAuth 인증 코드를 사용하여 액세스 토큰을 획득
        token_request = GetAccessTokenRequest(state=state, code=code)
        return GoogleOAuth2Service.refresh_access_token(token_request)

    @staticmethod
    def _fetch_user_profile(access_token: AccessToken) -> dict:
        # 액세스 토큰을 사용하여 사용자 프로필을 조회
        return GoogleOAuth2Service.fetch_user_profile(access_token)

    async def _create_or_update_account(self, user_profile: dict, session_id: str) -> None:
        # 사용자 프로필 정보를 기반으로 계정을 생성하거나 업데이트
        sso_id = user_profile.get("sub") or user_profile.get("id")
        if not sso_id:
            raise ValueError("User profile does not contain 'sub' or 'id' field")

        existing_account = account_usecase.get_account_by_oauth_id("GOOGLE", sso_id)

        if existing_account:
            # 기존 계정이 있는 경우, 변경된 필드만 업데이트
            self._update_account_if_changed(existing_account, user_profile)
        else:
            # 새 계정 생성
            await self._create_new_account(user_profile, sso_id, session_id)

    @staticmethod
    def _update_account_if_changed(existing_account, user_profile: dict) -> None:
        # 기존 계정의 정보가 변경된 경우에만 업데이트
        name = user_profile.get("name") or ""
        profile_image = user_profile.get("picture") or ""
        email = user_profile.get("email") or ""

        # 변경된 필드가 있는지 확인
        has_changes = (
            existing_account.name != name or
            existing_account.profile_image != profile_image or
            existing_account.email != email
        )

        if has_changes:
            update_request = CreateAccountRequest(
                oauth_id=existing_account.oauth_id,
                oauth_type=existing_account.oauth_type,
                nickname=existing_account.nickname,
                name=name,
                profile_image=profile_image,
                email=email,
                phone_number=existing_account.phone_number,
                active_status=existing_account.active_status,
                role_id=existing_account.role_id,
            )
            account_usecase.update(update_request)

    @staticmethod
    async def _create_new_account(user_profile: dict, sso_id: str, session_id:str) -> None:
        # 새로운 계정을 생성
        await account_usecase.create_account(
            session_id=session_id,
            oauth_id=sso_id,
            oauth_type="GOOGLE",
            nickname="",
            name=user_profile.get("name") or "",
            profile_image=user_profile.get("picture") or "",
            email=user_profile.get("email") or "",
            phone_number="",
            active_status="Y",
            role_id=""
        )
