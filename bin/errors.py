"""This module contains all custom errors/exceptions."""

from bin import constants


class CustomError(Exception):
    """A base class for all custom exceptions"""
    def __init__(self, message, exitcode):
        self._message = constants.BOLD + "ERROR: " + constants.NOBOLD + message
        self.exitcode = exitcode
        super().__init__()
    def getmessage(self):
        return constants.FAIL + self._message + constants.ENDC
    message = property(getmessage)


class FatalError(CustomError):
    """A custom exception for all errors that violate expected invariants"""
    def __init__(self, message):
        if message:
            msg = "Unkown Error"
        else:
            msg = message
        msg += "\n" + constants.WARNING + "That error should have "
        msg += constants.BOLD + "NEVER EVER" + constants.NOBOLD
        msg += " occur!! Please make sure to resolve this issue before"
        msg += " using this tool at all!" + constants.ENDC
        super().__init__(msg, 69)


class UserError(CustomError):
    """A custom exception for all errors that occur because the user called
    this progam with wrong arguments.
    Example: -i and -u where used in the same call"""
    def __init__(self, message):
        message += "\nUse --help for more information on how to use this tool."
        super().__init__(message, 101)


class IntegrityError(CustomError):
    """A custom exception for all errors that occur because there are logical/
    sematic errors in a profile written by the user.
    Example: A link is defined multiple times with different targets"""
    def __init__(self, message):
        super().__init__(message, 102)


class PreconditionError(CustomError):
    """A custom exception for all errors that occur due to preconditions
    or expectations that are not fullfilled
    Example: A link that is defined in the installed-file doesn't exist
    on the system"""
    def __init__(self, message):
        super().__init__(message, 103)


class GenerationError(CustomError):
    """A custom exception for all errors that occur during generation
    Example: The profile has syntax errors or is doing some nasty stuff"""
    def __init__(self, profileName, message):
        super().__init__(constants.BOLD + "[" + profileName + "]: " +
                         constants.NOBOLD + message, 104)


class UnkownError(CustomError):
    """A custom exception for all errors that are not expected/unkown
    Example: Used in a pokemon handler"""
    def __init__(self, originalError, message):
        message += "\nThe unkown error was:\n  "
        message += type(originalError).__name__ + ": " + str(originalError)
        super().__init__(message, 105)
