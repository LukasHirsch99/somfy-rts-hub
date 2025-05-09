class HubException(Exception):
    pass


class EmpytResponseException(HubException):
    pass


class InvalidOpcodeException(HubException):
    pass


class CoverNotFoundException(HubException):
    pass


class CoverAlreadyExistsException(HubException):
    pass


class CommandNotFoundException(HubException):
    pass


class InvalidStatusCodeException(HubException):
    pass


class NoMoreSpaceException(HubException):
    pass


class InternalHubException(HubException):
    pass
