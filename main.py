import flet as ft
import asyncio
import json
import time
from crypto_manager import CryptoManager
from webrtc_manager import WebRTCManager
from message_store import MessageStore


class ChatApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Secure P2P Chat"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 20
        
        self.crypto = CryptoManager()
        self.store = MessageStore()
        self.webrtc = None
        self.is_connected = False
        
        self.status_text = ft.Text("Not Connected", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.RED)
        self.chat_display = ft.ListView(expand=True, spacing=10, padding=10, auto_scroll=True)
        self.message_input = ft.TextField(hint_text="Type your message...", multiline=True, min_lines=1, max_lines=5, expand=True)
        self.ttl_input = ft.TextField(hint_text="Self-destruct (seconds)", width=150, keyboard_type=ft.KeyboardType.NUMBER)
        self.qr_image = ft.Image(visible=False, width=300, height=300, fit=ft.ImageFit.CONTAIN)
        
        self.build_ui()
        self.page.run_task(self.refresh_loop)
    
    def build_ui(self):
        header = ft.Container(
            content=ft.Row([ft.Icon(ft.icons.LOCK, color=ft.colors.GREEN), self.status_text]),
            padding=10, bgcolor=ft.colors.SURFACE_VARIANT, border_radius=10
        )
        
        input_row = ft.Row([
            self.message_input,
            ft.IconButton(icon=ft.icons.SEND, on_click=self.send_message, bgcolor=ft.colors.BLUE, icon_color=ft.colors.WHITE)
        ])
        
        ttl_row = ft.Row([ft.Icon(ft.icons.TIMER), self.ttl_input])
        
        action_buttons = ft.Row([
            ft.ElevatedButton("Pair via QR", icon=ft.icons.QR_CODE, on_click=self.start_pairing),
            ft.ElevatedButton("Scan QR", icon=ft.icons.CAMERA, on_click=self.scan_qr),
            ft.ElevatedButton("Wipe Chat", icon=ft.icons.DELETE_FOREVER, on_click=self.wipe_chat, bgcolor=ft.colors.RED)
        ], wrap=True)
        
        self.page.add(header, ft.Divider(), self.chat_display, ft.Divider(), ttl_row, input_row, action_buttons, self.qr_image)
    
    async def refresh_loop(self):
        while True:
            self.refresh_chat()
            await asyncio.sleep(1)
    
    def refresh_chat(self):
        messages = self.store.get_all()
        self.chat_display.controls.clear()
        
        for msg in messages:
            is_you = msg["sender"] == "You"
            time_left = ""
            if msg.get("expiry"):
                remaining = int(msg["expiry"] - time.time())
                if remaining > 0:
                    time_left = f" 🔥 {remaining}s"
            
            message_bubble = ft.Container(
                content=ft.Column([
                    ft.Text(msg["sender"], size=12, weight=ft.FontWeight.BOLD, 
                           color=ft.colors.BLUE if is_you else ft.colors.GREEN),
                    ft.Text(msg["message"] + time_left, size=14)
                ]),
                bgcolor=ft.colors.BLUE_100 if is_you else ft.colors.GREEN_100,
                padding=10, border_radius=10,
                alignment=ft.alignment.center_right if is_you else ft.alignment.center_left
            )
            self.chat_display.controls.append(message_bubble)
        
        self.page.update()
    
    def send_message(self, e):
        msg = self.message_input.value.strip()
        if not msg or not self.is_connected:
            return
        
        ttl = None
        if self.ttl_input.value.strip().isdigit():
            ttl = int(self.ttl_input.value.strip())
        
        self.webrtc.send_message(msg, ttl)
        self.store.add("You", msg, ttl)
        self.message_input.value = ""
        self.ttl_input.value = ""
        self.refresh_chat()
    
    def start_pairing(self, e):
        self.page.run_task(self.async_generate_qr)
    
    async def async_generate_qr(self):
        if not self.webrtc:
            self.webrtc = WebRTCManager(self.crypto, self.on_message_received, self.on_remote_wipe)
        
        offer = await self.webrtc.create_offer()
        
        import qrcode, io, base64
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(offer)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode()
        
        self.qr_image.src_base64 = img_base64
        self.qr_image.visible = True
        self.status_text.value = "Show QR to peer, then scan their QR"
        self.status_text.color = ft.colors.ORANGE
        self.page.update()
    
    def scan_qr(self, e):
        def on_file_picked(e: ft.FilePickerResultEvent):
            if e.files:
                self.page.run_task(self.process_qr_image, e.files[0].path)
        
        file_picker = ft.FilePicker(on_result=on_file_picked)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(allowed_extensions=["png", "jpg", "jpeg"], dialog_title="Select QR Code Image")
    
    async def process_qr_image(self, image_path):
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            img = Image.open(image_path)
            decoded = decode(img)
            
            if decoded:
                answer_sdp = decoded[0].data.decode()
                
                if self.webrtc.pc.localDescription:
                    await self.webrtc.receive_answer(answer_sdp)
                else:
                    answer = await self.webrtc.receive_offer(answer_sdp)
                    import qrcode, io, base64
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(answer)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    buffer.seek(0)
                    img_base64 = base64.b64encode(buffer.read()).decode()
                    self.qr_image.src_base64 = img_base64
                    self.qr_image.visible = True
                
                self.is_connected = True
                self.status_text.value = "Connected Securely 🔒"
                self.status_text.color = ft.colors.GREEN
                self.qr_image.visible = False
                self.page.update()
        except Exception as ex:
            self.status_text.value = f"QR scan failed: {ex}"
            self.page.update()
    
    def on_message_received(self, message: str, ttl=None):
        self.store.add("Peer", message, ttl)
        self.refresh_chat()
    
    def on_remote_wipe(self):
        self.store.delete_all()
        self.status_text.value = "Chat wiped by peer 🔥"
        self.status_text.color = ft.colors.RED
        self.refresh_chat()
    
    def wipe_chat(self, e):
        if self.webrtc and self.is_connected:
            self.webrtc.send_wipe()
        self.store.delete_all()
        self.status_text.value = "Chat wiped 🔥"
        self.status_text.color = ft.colors.RED
        self.refresh_chat()


def main(page: ft.Page):
    ChatApp(page)


if __name__ == "__main__":
    ft.app(target=main)
