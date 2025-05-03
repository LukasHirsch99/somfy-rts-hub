from __future__ import annotations
import asyncio
from asyncio import StreamReader, StreamWriter
import logging
from dataclasses import dataclass
import struct
from .const import ReqBody, CMD, OP_CODE
from .cover import Cover
from .errors import InvalidResponseException, InvalidOpcodeException


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
    RES_HEADER_SIZE = 2
    COVER_FMT = f"<II{MAX_NAME_LEN}s"

    def __init__(self, host: str, port: int) -> None:
        """Initialize the SomfyHub Object with it's host and port."""
        self.host = host
        self.port = port
        self.writer: StreamWriter = None
        self.reader: StreamReader = None

    async def _connect(self) -> bool:
        _LOGGER.info("Connection to: %s:%s", self.host, self.port)
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port
        )

    def _parseResHeader(self, r: bytes) -> tuple[int, int]:
        return struct.unpack("<BB", r[:self.RES_HEADER_SIZE])

    def _parseResCover(self, r: bytes) -> Cover:
        remoteId, rc, name = struct.unpack(self.COVER_FMT, r)
        return Cover(
            self, name.split(b'\x00', 1)[0].decode('ascii'), remoteId, rc
        )

    def _buildHeader(self, opcode: OP_CODE):
        return struct.pack("<HB", MAGIC_NUM, opcode.value)

    async def _sendRequest(
        self, opcode: OP_CODE, body: ReqBody = None
    ) -> tuple[int, bytes]:
        """Send a request containing opcode and optional body to hub.
        returns the status and optional body.
        throws:
        InvalidOpcodeException, when the response doesn't belong to the request
        EmpytResponseException, when no response has been received
        """
        if self.writer is None or self.writer.is_closing():
            await self._connect()

        data = self._buildHeader(opcode)
        if body:
            data += body._toBytes()

        self.writer.write(data)
        await self.writer.drain()

        rb = await self.reader.read(1024)
        if len(rb) < 1:
            raise EmpytResponseException("ERROR: empty response")

        op, status = self._parseResHeader(rb)

        if op != opcode.value | 0x80:
            raise InvalidOpcodeException(
                f"ERROR: wrong opcode {hex(op)} expected: {hex(opcode.value | 0x80)}")

        return status, rb[self.RES_HEADER_SIZE:]

    async def getAllCovers(self) -> list[Cover]:
        """Returns a list of Cover's safed on the hub"""
        status, body = await self._sendRequest(OP_CODE.GET_COVERS)

        if status != 0:
            raise Exception(f"ERROR: Unknown error, status: {status}")

        count = body[0]
        COVER_SIZE = struct.calcsize(self.COVER_FMT)

        if len(body) != 1 + count * COVER_SIZE:
            raise Exception(f"ERROR: invalid length {body}")

        covers: list[Cover] = []
        for i in range(1, len(body), COVER_SIZE):
            chunk = body[i:i + COVER_SIZE]
            if len(chunk) != COVER_SIZE:
                break
            covers.append(self._parseResCover(chunk))

        return covers

    async def _sendCmd(self, remoteId: int, cmd: CMD) -> None:
        """Send command to cover identified with remoteId.
        """
        status, _ = await self._sendRequest(
            OP_CODE.COVER_CMD, ReqCoverCmd(remoteId, cmd)
        )
        if status == 1:
            raise Exception(f"ERROR: Cover with remoteId: {
                            remoteId} not found")
        if status == 2:
            raise Exception(f"ERROR: Invalid command: {cmd} not found")
        if status != 0:
            raise Exception(f"ERROR: Unknown error, status: {status}")

    async def addCover(
        self, name: str, remoteId: int = 0, rollingCode: int = 0
    ) -> Cover:
        """Creates and stores a new cover on the hub.
        The hub broadcasts a 'PROG' command, and covers which are in PROG mode,
        will add the remote to their storage.
        """
        status, body = await self._sendRequest(
            OP_CODE.ADD_COVER, ReqAddCover(name, remoteId, rollingCode)
        )

        if status == 1:
            raise Exception(f"ERROR: Cover with name: {
                            name} already exits")
        if status == 2:
            raise Exception(f"ERROR: Cover with remoteId: {
                            remoteId} already exits")
        if status == 3:
            raise Exception("ERROR: No more cover space available")
        if status != 0:
            raise Exception(f"ERROR: Unknown error, status: {status}")

        return self._parseResCover(body)

    async def renameCover(self, remoteId: int, name: str) -> None:
        """Rename a cover identified by remoteId and safes the name on the hub.
        """
        status, _ = await self._sendRequest(OP_CODE.REN_COVER, ReqRenCover(remoteId, name))

        if status == 1:
            raise Exception(f"ERROR: Cover with remoteId: {
                            remoteId} not found")
        if status == 2:
            raise Exception(
                "ERROR: Failed to update name")
        if status != 0:
            raise Exception(f"ERROR: Unknown error, status: {status}")

    async def removeCover(self, remoteId: int) -> None:
        """Remove a cover identified by remoteId from the hub.
        The hub broadcasts a 'DEL' command, and covers which are in PROG mode,
        will remove the remote from their storage.
        """
        await self._sendCmd(remoteId, CMD.DEL)

    async def customCommand(
        self, remoteId: int, rollingCode: int, command: CMD, frameRepeat: int
    ) -> None:
        """Hub sends a custom command specified by remoteId, rollingCode,
        command and frameRepeat.
        remoteId: custom remoteId
        rollingCode: custom rollingCode
        frameRepeat: how long the button is pressed
        """
        status, _ = await self._sendRequest(
            OP_CODE.CUSTOM_CMD,
            ReqCustomCmd(remoteId, rollingCode, command, frameRepeat),
        )

        if status != 0:
            raise Exception(f"ERROR: Unknown error, status: {status}")
