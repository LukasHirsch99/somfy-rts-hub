from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from enum import Enum
from dataclasses import dataclass


class RES_STATUS(Enum):
    SUCCESS = 0
    ERROR = 1
    UNKNOWN = 2


T = TypeVar('T')


@dataclass
class Res(Generic[T]):
    status: RES_STATUS
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
