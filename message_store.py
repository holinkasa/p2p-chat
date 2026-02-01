import time


class MessageStore:
    def __init__(self):
        self.messages = []
    
    def add(self, sender: str, message: str, ttl: int = None):
        expiry = time.time() + ttl if ttl else None
        self.messages.append({"sender": sender, "message": message, "expiry": expiry})
    
    def delete_all(self):
        self.messages.clear()
    
    def cleanup_expired(self):
        now = time.time()
        self.messages = [m for m in self.messages if not m.get("expiry") or m["expiry"] > now]
    
    def get_all(self):
        self.cleanup_expired()
        return self.messages
