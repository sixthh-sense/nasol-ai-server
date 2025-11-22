from abc import ABC, abstractmethod

class AccountRepositoryPort(ABC):

    ## 임시
    @abstractmethod
    def get_account_by_id(self, oauth_id: str):
        pass