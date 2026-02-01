import nacl.utils
from nacl.public import PrivateKey, PublicKey, Box
from nacl.secret import SecretBox
from nacl.hash import blake2b
from nacl.encoding import RawEncoder


class CryptoManager:
    def __init__(self):
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key
        self.session_box = None
    
    def get_public_key_bytes(self) -> bytes:
        return bytes(self.public_key)
    
    def generate_shared_secret(self, peer_public_key_bytes: bytes):
        peer_key = PublicKey(peer_public_key_bytes)
        box = Box(self.private_key, peer_key)
        shared = box.shared_key()
        session_key = blake2b(shared, encoder=RawEncoder, digest_size=32)
        self.session_box = SecretBox(session_key)
    
    def encrypt(self, plaintext: bytes) -> bytes:
        if not self.session_box:
            raise RuntimeError("Session key not established")
        return self.session_box.encrypt(plaintext)
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        if not self.session_box:
            raise RuntimeError("Session key not established")
        return self.session_box.decrypt(ciphertext)
