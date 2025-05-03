from __future__ import annotations
from .const import CMD
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hub import Hub


class Cover:
    def __init__(
        self, api: Hub, name: str, remoteId: str, rollingCode: str
    ) -> None:
        self.api = api
        self.name = name
        self.remoteId = int(remoteId)
        self.rollingCode = int(rollingCode)

    def __str__(self):
        return f"(name: {self.name}, remoteId: {self.remoteId}, rc: {
            self.rollingCode})"

    async def open(self):
        """Open the cover."""
        return await self.api._sendCmd(self.remoteId, CMD.UP)

    async def close(self):
        """Close the cover."""
        return await self.api._sendCmd(self.remoteId, CMD.DOWN)

    async def stop(self):
        """Stop the cover in its current position."""
        return await self.api._sendCmd(self.remoteId, CMD.STOP)

    async def rename(self, newName: str):
        """Rename the cover."""
        await self.api.renameCover(self.remoteId, newName)
        self.name = newName
