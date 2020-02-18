"""This module contains all custom errors/exceptions.

.. autosummary::
    :nosignatures:

    CustomError
    FatalError
    GenerationError
    IntegrityError
    PreconditionError
    UnkownError
    UserAbortion
    UserError
"""

###############################################################################
#
# Copyright 2020 Erik Schulz
#
# This file is part of uberdot.
#
# uberdot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# uberdot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with uberdot.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################


from abc import abstractmethod
from uberdot import constants as const


class CustomError(Exception):
    """A base class for all custom exceptions.

    Attributes:
        _message (str): The original unformated error message
        message (str): The formatted colored error message
    """
    def __init__(self, message):
        """Constructor

        Args:
            message (str): The error message
        """
        self._message = message
        super().__init__()

    @property
    @abstractmethod
    def EXITCODE(self):
        """The exitcode that will be returned when this exception is raised.
        This needs to be implemented by subclasses.
        """
        raise NotImplementedError

    @property
    def message(self):
        msg = const.col_fail + const.col_emph + "ERROR: " + const.col_endc
        msg += const.col_fail + self._message + const.col_endc
        return msg


class FatalError(CustomError):
    """A custom exception for all errors that violate expected invariants."""

    EXITCODE = 69
    """The exitcode for a FatalError"""

    def __init__(self, message="Unkown Error"):
        """Constructor.

        Adds a disclaimer that this error is indeed really bad.

        Args:
            message (str): The error message
        """
        msg = message
        msg += "\n" + const.col_warning + "This error should NEVER EVER "
        msg += "occur!! The developer fucked this up really hard! Please "
        msg += "make sure to resolve this issue before using this "
        msg += "tool again!" + const.col_endc
        super().__init__(msg)


class UserError(CustomError):
    """A custom exception for all errors that occur because the user didn't
    used the program correctly.

    :Example: --parent was specified without using -i.
    """

    EXITCODE = 101
    """The exitcode for a UserError"""

    def __init__(self, message):
        """Constructor.

        Adds a hint how to show help.

        Args:
            message (str): The error message
        """
        message += "\nUse --help for more information on how to use this tool."
        super().__init__(message)


class IntegrityError(CustomError):
    """A custom exception for all errors that occur because there are logical/
    sematic errors in a profile written by the user.

    :Example: A link is defined multiple times with different targets.
    """

    EXITCODE = 102
    """The exitcode for a IntegrityError"""


class PreconditionError(CustomError):
    """A custom exception for all errors that occur due to preconditions
    or expectations that are not fullfilled.

    :Example: A link that is defined in the installed-file doesn't exist
        on the system.
    """

    EXITCODE = 103
    """The exitcode for a PreconditionError"""


class GenerationError(CustomError):
    """A custom exception for all errors that occur during generation.

    :Example: The profile has syntax errors or a dotfile can't be found.
    """

    EXITCODE = 104
    """The exitcode for a GenerationError"""

    def __init__(self, profile_name, message):
        """Constructor.

        Adds the name of the profile that triggered the error to the message.

        Args:
            profile_name (str): Name of the profile that triggered the error
            message (str): The error message
        """
        super().__init__(const.col_emph + "[" + profile_name + "]: " +
                         const.col_endc + message)


class UnkownError(CustomError):
    """A custom exception for all errors that are not expected/unkown.

    Used in pokemon handlers of critical sections to convert all unexpected
    errors into CustomException.
    """

    EXITCODE = 105
    """The exitcode for a UnkownError"""

    def __init__(self, original_error, message):
        """Constructor.

        Adds the type and the message of the original error to the error
        message.

        Args:
            original_error (Exception): The original exception that was catched
            message (str): An additional message for context
        """
        message += "\nThe unkown error was:\n  "
        message += type(original_error).__name__
        if str(original_error):
            message += ": " + str(original_error)
        super().__init__(message)


class UserAbortion(CustomError):
    """Used to abort uberdot at any given point safely by the user."""

    EXITCODE = 106
    """The exitcode for a UserAbortion"""

    def __init__(self):
        """Constructor.

        Sets the error message to "Aborted by user".
        """
        super().__init__("Aborted by user")


class SystemAbortion(CustomError):
    """Used to abort uberdot by the system."""

    EXITCODE = 107
    """The exitcode for a SystemAbortion"""
