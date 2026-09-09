from pypresence import Presence

from ..config import CLIENT_ID


class DiscordRPC:
    def __init__(self, client_id: str = CLIENT_ID):
        self.client_id = client_id
        self.rpc = Presence(client_id)

    def connect(self):
        return self.rpc.connect()

    def update(self, details: str, state: str, large_image: str, large_text: str, start: int):
        self.rpc.update(
            details=details,
            state=state,
            large_image=large_image,
            large_text=large_text,
            start=start,
        )

    def close(self):
        try:
            self.rpc.close()
        except Exception:
            pass
