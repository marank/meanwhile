"""
Talking to the ASGI application in tests, like Channels' communicators (channels.testing), which
can't be imported without daphne, a server the app doesn't use.
"""

import json
from typing import Any
from unittest import mock

from asgiref.testing import ApplicationCommunicator

from config.asgi import application


class Communicator(ApplicationCommunicator):
    """Keeps the test's database connection open: Channels would close it between messages.

    asgiref's communicator has no type annotations; its calls are typed here, once.
    """

    def __init__(self, scope: dict[str, Any]) -> None:
        super().__init__(application, scope)  # type: ignore[no-untyped-call]  # asgiref is untyped

    async def send_input(self, message: dict[str, Any]) -> None:
        with mock.patch("channels.db.close_old_connections", return_value=None):
            await super().send_input(message)  # type: ignore[no-untyped-call]  # asgiref is untyped

    async def receive_output(self, timeout: float = 1) -> dict[str, Any]:
        with mock.patch("channels.db.close_old_connections", return_value=None):
            output: dict[str, Any] = await super().receive_output(timeout)  # type: ignore[no-untyped-call]  # asgiref is untyped
            return output

    async def receive_nothing(self, timeout: float = 0.1, interval: float = 0.01) -> bool:
        nothing: bool = await super().receive_nothing(timeout, interval)  # type: ignore[no-untyped-call]  # asgiref is untyped
        return nothing

    async def wait(self, timeout: float = 1) -> None:
        await super().wait(timeout)  # type: ignore[no-untyped-call]  # asgiref is untyped


class WebsocketCommunicator(Communicator):
    def __init__(self, path: str, *, headers: list[tuple[bytes, bytes]]) -> None:
        super().__init__(
            {"type": "websocket", "path": path, "query_string": b"", "headers": headers, "subprotocols": []}
        )

    async def connect(self) -> tuple[bool, int | None]:
        """(True, None) when the socket is accepted, (False, close code) when it is refused."""
        await self.send_input({"type": "websocket.connect"})
        response = await self.receive_output()
        if response["type"] == "websocket.close":
            return False, response.get("code", 1000)
        assert response["type"] == "websocket.accept"
        return True, None

    async def send_to(self, text_data: str) -> None:
        await self.send_input({"type": "websocket.receive", "text": text_data})

    async def send_json_to(self, data: object) -> None:
        await self.send_to(json.dumps(data))

    async def receive_json_from(self) -> Any:
        response = await self.receive_output()
        assert response["type"] == "websocket.send", response
        return json.loads(response["text"])

    async def disconnect(self, code: int = 1000) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(1)


class HttpCommunicator(Communicator):
    def __init__(self, method: str, path: str, *, headers: list[tuple[bytes, bytes]], body: bytes = b"") -> None:
        scope: dict[str, Any] = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": headers,
        }
        super().__init__(scope)
        self.body = body

    async def get_response(self, timeout: float = 1) -> dict[str, Any]:
        """The status, headers and whole body of the response."""
        await self.send_input({"type": "http.request", "body": self.body})
        response = await self.receive_output(timeout)
        assert response["type"] == "http.response.start"
        body = b""
        while True:
            chunk = await self.receive_output(timeout)
            body += chunk["body"]
            if not chunk.get("more_body", False):
                return {"status": response["status"], "headers": response.get("headers", []), "body": body}
