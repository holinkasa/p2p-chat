import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from aiortc.contrib.signaling import object_to_string, object_from_string


class WebRTCManager:
    def __init__(self, crypto_manager, on_message_callback, on_wipe_callback):
        self.pc = RTCPeerConnection()
        self.crypto = crypto_manager
        self.channel = None
        self.on_message = on_message_callback
        self.on_wipe = on_wipe_callback
        
        @self.pc.on("datachannel")
        def on_datachannel(channel: RTCDataChannel):
            self.channel = channel
            self._setup_channel()
    
    def _setup_channel(self):
        @self.channel.on("message")
        def on_message(data):
            try:
                decrypted = self.crypto.decrypt(data)
                payload = json.loads(decrypted.decode())
                
                if payload["type"] == "msg":
                    self.on_message(payload["content"], payload.get("ttl"))
                elif payload["type"] == "wipe":
                    self.on_wipe()
                elif payload["type"] == "pubkey":
                    peer_pubkey = bytes.fromhex(payload["pubkey"])
                    self.crypto.generate_shared_secret(peer_pubkey)
            except Exception as e:
                print(f"Error handling message: {e}")
    
    async def create_offer(self) -> str:
        self.channel = self.pc.createDataChannel("chat")
        self._setup_channel()
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        offer_data = {
            "sdp": object_to_string(self.pc.localDescription),
            "pubkey": self.crypto.get_public_key_bytes().hex()
        }
        return json.dumps(offer_data)
    
    async def receive_offer(self, offer_json: str) -> str:
        offer_data = json.loads(offer_json)
        peer_pubkey = bytes.fromhex(offer_data["pubkey"])
        self.crypto.generate_shared_secret(peer_pubkey)
        offer = object_from_string(offer_data["sdp"])
        await self.pc.setRemoteDescription(offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        answer_data = {
            "sdp": object_to_string(self.pc.localDescription),
            "pubkey": self.crypto.get_public_key_bytes().hex()
        }
        return json.dumps(answer_data)
    
    async def receive_answer(self, answer_json: str):
        answer_data = json.loads(answer_json)
        peer_pubkey = bytes.fromhex(answer_data["pubkey"])
        self.crypto.generate_shared_secret(peer_pubkey)
        answer = object_from_string(answer_data["sdp"])
        await self.pc.setRemoteDescription(answer)
    
    def send_message(self, message: str, ttl=None):
        if not self.channel:
            raise RuntimeError("Data channel not established")
        payload = {"type": "msg", "content": message, "ttl": ttl}
        encrypted = self.crypto.encrypt(json.dumps(payload).encode())
        self.channel.send(encrypted)
    
    def send_wipe(self):
        if not self.channel:
            raise RuntimeError("Data channel not established")
        payload = {"type": "wipe"}
        encrypted = self.crypto.encrypt(json.dumps(payload).encode())
        self.channel.send(encrypted)
