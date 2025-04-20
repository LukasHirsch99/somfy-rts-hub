from abc import ABC, abstractmethod
import asyncio
from asyncio import StreamReader, StreamWriter
from enum import Enum
import logging
from dataclasses import dataclass

from typing import TypeVar, Generic

_LOGGER = logging.getLogger(__name__)

MAGIC_NUM = 0xAFFE


def _toLittleEndianBytes(v, n: int):
    """Helper function which converts v to little endian with n bytes."""
    return v.to_bytes(n, byteorder="little")


class STATUS(Enum):
    SUCCESS = 0
    ERROR = 1
    UNKNOWN = 2


T = TypeVar('T')


@dataclass
class Res(Generic[T]):
    status: STATUS
    body: T


class CMD(Enum):
    """Cover commands."""

    STOP = 0x1
    UP = 0x2
    DOWN = 0x4
    PROG = 0x8
    DEL = 0x8


class OP_CODE(Enum):
    """Hub opcodes."""

    GET_COVERS = 0x1
    COVER_CMD = 0x2
    ADD_COVER = 0x3
    REN_COVER = 0x4
    CUSTOM_CMD = 0x5


class ReqBody(ABC):
    """Abstractclass for Request Body."""

    @abstractmethod
    def _toBytes(self):
        pass


class ReqCoverCmd(ReqBody):
    """Body for cover command."""

    def __init__(self, cmd: CMD) -> None:
        self.cmd = cmd

    def _toBytes(self):
        return _toLittleEndianBytes(self.cmd.value, 1)


class ReqGetCovers(ReqBody):
    """Class for empty body"""

    def _toBytes(self):
        return b""


class ReqAddCover(ReqBody):
    """Body for adding cover"""

    def __init__(self, name: str, rollingCode: int = 0) -> None:
        self.name = name
        self.rollingCode = rollingCode

    def _toBytes(self):
        return (
            _toLittleEndianBytes(self.rollingCode, 4)
            + _toLittleEndianBytes(len(self.name) + 1, 1)
            + bytes(self.name + "\0", encoding="ascii")
        )


class ReqRenCover(ReqBody):
    """Body for renaming cover"""

    def __init__(self, name: str) -> None:
        self.name = name

    def _toBytes(self):
        return _toLittleEndianBytes(len(self.name) + 1, 1) + bytes(
            self.name + "\0", encoding="ascii"
        )


class ReqCustomCmd(ReqBody):
    """Body for custom command"""

    def __init__(self, rollingCode: int, command: CMD, frameRepeat: int) -> None:
        self.rollingCode = rollingCode
        self.command = command
        self.frameRepeat = frameRepeat

    def _toBytes(self):
        return (
            _toLittleEndianBytes(self.rollingCode, 4)
            + _toLittleEndianBytes(self.command, 1)
            + _toLittleEndianBytes(self.frameRepeat, 2)
        )


class SomfyApiCover:
    def __init__(
        self, api: "SomfyHub", name: str, remoteId: str, rollingCode: str
    ) -> None:
        self.api = api
        self.name = name
        self.remoteId = int(remoteId)
        self.rollingCode = int(rollingCode)

    def __str__(self):
        return f"(name: {self.name}, remoteId: {self.remoteId}, rc: {self.rollingCode})"

    async def open(self):
        return await self.api._sendCmd(self.remoteId, CMD.UP)

    async def close(self):
        return await self.api._sendCmd(self.remoteId, CMD.DOWN)

    async def stop(self):
        return await self.api._sendCmd(self.remoteId, CMD.STOP)


class SomfyHub:
    def __init__(self, host: str, port: int) -> None:
        """Initialize the SomfyHub Object with it's host and port."""
        self.host = host
        self.port = port
        self.writer: StreamWriter | None = None
        self.reader: StreamReader | None = None

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

    def _buildHeader(self, opcode: OP_CODE, remoteId: int = 0):
        return (
            _toLittleEndianBytes(MAGIC_NUM, 2)
            + _toLittleEndianBytes(opcode.value, 2)
            + _toLittleEndianBytes(remoteId, 4)
        )

    async def _sendRequestWithoutBody(self, opcode: OP_CODE) -> Res[str]:
        """Send a request without a body, this is used for getAllCovers()"""
        return await self._sendRequest(opcode, 0, ReqGetCovers())

    async def _sendRequest(
        self, opcode: OP_CODE, remoteId: int, body: ReqBody
    ) -> Res[str]:
        """Send a request containing remoteId and body
        returns a tuple(err: int, msg: str)
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        if self.writer is None or self.writer.is_closing():
            if not await self._connect():
                return Res(STATUS.ERROR, "connection to somfy-remote failed")

        assert self.writer is not None
        assert self.reader is not None

        data = self._buildHeader(opcode, remoteId)
        if body:
            data += body._toBytes()

        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            _LOGGER.error("Write error: %s", e)
            return Res(STATUS.ERROR, f"Write error: {e}")
        try:
            rb = await self.reader.read(1024)
            r = rb.decode("ascii")
            if len(r) < 1:
                return Res(STATUS.ERROR, f"invalid response: '{r}'")

            # return (int(r[0]), r[1:])
            return Res(STATUS(int(r[0])), r[1:])

        except Exception as e:
            _LOGGER.error("Read error: %s", e)
            return Res(STATUS.ERROR, f"Read error: {e}")

    async def getAllCovers(self) -> Res[list[SomfyApiCover]]:
        """Returns a list of SomfyApiCover's safed on the hub"""
        r = await self._sendRequestWithoutBody(OP_CODE.GET_COVERS)
        if r.status != STATUS.SUCCESS:
            return r
        if r.body is None:
            return Res[list[SomfyApiCover]](STATUS.SUCCESS, [])
        return Res[list[SomfyApiCover]](STATUS.SUCCESS, [
            SomfyApiCover(self, *row.split(";")) for row in r.body.splitlines() if row
        ])

    async def _sendCmd(self, remoteId: int, cmd: CMD) -> Res[str]:
        """Send command to cover identified with remoteId.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.COVER_CMD, remoteId, ReqCoverCmd(cmd))

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
            OP_CODE.ADD_COVER, remoteId, ReqAddCover(name, rollingCode)
        )

    async def renameCover(self, remoteId: int, name: str) -> Res[str]:
        """Renames a cover identified by remoteId and safes the name on the hub.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.REN_COVER, remoteId, ReqRenCover(name))

    async def removeCover(self, remoteId: int) -> Res[str]:
        """Removes a cover identified by remoteId from the hub.
        The hub broadcasts a 'DEL' command, and covers which are in PROG mode,
        will remove the remote from their storage.
        returns Res[msg: str]
        err: the error-code, 0 = success, 1 = error, 2 unknown error
        msg: the response or error-message
        """
        return await self._sendRequest(OP_CODE.COVER_CMD, remoteId, ReqCoverCmd(CMD.DEL))

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
            remoteId,
            ReqCustomCmd(rollingCode, command, frameRepeat),
        )
