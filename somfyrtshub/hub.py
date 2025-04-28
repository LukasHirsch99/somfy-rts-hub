from __future__ import annotations
import asyncio
from asyncio import StreamReader, StreamWriter
import logging
from dataclasses import dataclass
import struct
from .const import ReqBody, CMD, OP_CODE, Res, RES_STATUS

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cover import Cover


_LOGGER = logging.getLogger(__name__)

MAGIC_NUM = 0xAFFE
MAX_NAME_LEN = 30


@dataclass
class ReqCoverCmd(ReqBody):
    """Body for sending a command to a cover."""

    remoteId: int
    cmd: CMD

    def _toBytes(self):
        return struct.pack("<IB", self.remoteId, self.cmd.value)


@dataclass
class ReqAddCover(ReqBody):
    """Body for adding cover"""

    name: str
    remoteId: int = 0
    rollingCode: int = 0

    def _toBytes(self):
        name_bytes = self.name.encode("utf-8")
        name_bytes = name_bytes.ljust(
            MAX_NAME_LEN, b'\0')  # pad with \0 to 30 bytes
        return struct.pack(f"<II{MAX_NAME_LEN}s", self.remoteId, self.rollingCode, name_bytes)


@dataclass
class ReqRenCover(ReqBody):
    """Body for renaming cover"""

    remoteId: int
    name: str

    def _toBytes(self):
        name_bytes = self.name.encode("utf-8")
        name_bytes = name_bytes.ljust(
            MAX_NAME_LEN, b'\0')  # pad with \0 to 30 bytes
        return struct.pack(f"<I{MAX_NAME_LEN}s", self.remoteId, name_bytes)


@dataclass
class ReqCustomCmd(ReqBody):
    """Body for custom command"""

    remoteId: int
    rollingCode: int
    command: CMD
    frameRepeat: int

    def _toBytes(self):
        return struct.pack("<IIBB", self.remoteId, self.rollingCode, self.command.value, self.frameRepeat)


class Hub:
    """This class talks and configures the ESP remote."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the SomfyHub Object with it's host and port."""
        self.host = host
        self.port = port
        self.writer: StreamWriter = None
        self.reader: StreamReader = None

    async def _connect(self) -> bool:
        _LOGGER.info("Connection to: %s:%s", self.host, self.port)
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            return True
        except Exception as e:
            _LOGGER.error("Connection failed: %e", e)
            return False

    def _buildHeader(self, opcode: OP_CODE):
        return struct.pack("<HB", MAGIC_NUM, opcode.value)

    async def _sendRequest(
        self, opcode: OP_CODE, body: ReqBody = None
    ) -> Res[str]:
        """Send a request containing remoteId and body
        returns a Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        if self.writer is None or self.writer.is_closing():
            if not await self._connect():
                return Res(RES_STATUS.ERROR, "connection to hub failed")

        data = self._buildHeader(opcode)
        if body:
            data += body._toBytes()

        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            _LOGGER.error("Write error: %s", e)
            return Res(RES_STATUS.ERROR, f"Write error: {e}")

        try:
            rb = await self.reader.read(1024)
            r = rb.decode("ascii")
            if len(r) < 1:
                return Res(RES_STATUS.ERROR, f"invalid response: '{r}'")

            return Res(RES_STATUS(int(r[0])), r[1:])

        except Exception as e:
            _LOGGER.error("Read error: %s", e)
            return Res(RES_STATUS.ERROR, f"Read error: {e}")

    async def getAllCovers(self) -> Res[list[Cover]]:
        """Returns a list of SomfyApiCover's safed on the hub"""
        r = await self._sendRequest(OP_CODE.GET_COVERS)
        if r.status != RES_STATUS.SUCCESS:
            return r
        if r.body is None:
            return Res[list[Cover]](RES_STATUS.SUCCESS, [])
        return Res[list[Cover]](RES_STATUS.SUCCESS, [
            Cover(self, *row.split(";")) for row in r.body.splitlines() if row
        ])

    async def _sendCmd(self, remoteId: int, cmd: CMD) -> Res[str]:
        """Send command to cover identified with remoteId.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.COVER_CMD, ReqCoverCmd(remoteId, cmd))

    async def addCover(
        self, name: str, remoteId: int = 0, rollingCode: int = 0
    ) -> Res[str]:
        """Creates and stores a new cover on the hub.
        The hub broadcasts a 'PROG' command, and covers which are in PROG mode,
        will add the remote to their storage.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(
            OP_CODE.ADD_COVER, ReqAddCover(name, remoteId, rollingCode)
        )

    async def renameCover(self, remoteId: int, name: str) -> Res[str]:
        """Renames a cover identified by remoteId and safes the name on the hub.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.REN_COVER, ReqRenCover(remoteId, name))

    async def removeCover(self, remoteId: int) -> Res[str]:
        """Removes a cover identified by remoteId from the hub.
        The hub broadcasts a 'DEL' command, and covers which are in PROG mode,
        will remove the remote from their storage.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.COVER_CMD, ReqCoverCmd(remoteId, CMD.DEL))

    async def customCommand(
        self, remoteId: int, rollingCode: int, command: CMD, frameRepeat: int
    ) -> Res[str]:
        """Hub sends a custom command specified by remoteId, rollingCode, command and frameRepeat.
        frameRepeat: how long the button is pressed
        returns a tuple(err: int, msg: str)
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(
            OP_CODE.CUSTOM_CMD,
            ReqCustomCmd(remoteId, rollingCode, command, frameRepeat),
        )
