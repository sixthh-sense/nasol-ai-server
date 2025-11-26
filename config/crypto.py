from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64

# 1. 키와 IV 생성 (안전을 위해 임의로 생성)
key = get_random_bytes(16) # 128비트 키
iv = get_random_bytes(16)  # 128비트 IV

class Crypto:
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
        self.key = key
        self.iv = iv

    @staticmethod
    def enc_data(target_text: str):
        data_bytes = target_text.encode('utf-8')

        # 3. AES 객체 생성 및 암호화 (CBC 모드 사용)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(data_bytes, AES.block_size)  # 블록 크기에 맞춰 패딩
        encrypted_data = cipher.encrypt(padded_data)

        encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
        return encrypted_b64

    @staticmethod
    def dec_data(target_text: str):
        encrypted_bytes = base64.b64decode(target_text)

        # 6. 복호화 객체 생성
        cipher_decrypt = AES.new(key, AES.MODE_CBC, iv)

        # 7. 복호화 및 패딩 제거
        decrypted_padded_bytes = cipher_decrypt.decrypt(encrypted_bytes)
        decrypted_bytes = unpad(decrypted_padded_bytes, AES.block_size)

        # 8. 바이트를 문자열로 변환
        decrypted_data = decrypted_bytes.decode('utf-8')
        return decrypted_data