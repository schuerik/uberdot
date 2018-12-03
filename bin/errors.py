"""This module contains all custom errors/exceptions."""

###############################################################################
#
# Copyright 2018 Erik Schulz
#
# This file is part of Dotmanager.
#
# Dotmanger is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dotmanger is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Dotmanger.  If not, see <http://www.gnu.org/licenses/>.
#
# Diese Datei ist Teil von Dotmanger.
#
# Dotmanger ist Freie Software: Sie können es unter den Bedingungen
# der GNU General Public License, wie von der Free Software Foundation,
# Version 3 der Lizenz oder (nach Ihrer Wahl) jeder neueren
# veröffentlichten Version, weiter verteilen und/oder modifizieren.
#
# Dotmanger wird in der Hoffnung, dass es nützlich sein wird, aber
# OHNE JEDE GEWÄHRLEISTUNG, bereitgestellt; sogar ohne die implizite
# Gewährleistung der MARKTFÄHIGKEIT oder EIGNUNG FÜR EINEN BESTIMMTEN ZWECK.
# Siehe die GNU General Public License für weitere Details.
#
# Sie sollten eine Kopie der GNU General Public License zusammen mit diesem
# Programm erhalten haben. Wenn nicht, siehe <https://www.gnu.org/licenses/>.
#
###############################################################################


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
        if not message:
            msg = "Unkown Error"
        else:
            msg = message
        msg += "\n" + constants.WARNING + "That error should have "
        msg += constants.BOLD + "NEVER EVER" + constants.NOBOLD + " "
        msg += "occur!! The developer fucked this up really hard! Please "
        msg += "make sure to resolve this issue before using this "
        msg += "tool at all!" + constants.ENDC
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


class UserAbortion(CustomError):
    """Used to abort the dotmanager at any given point safely by the user"""
    def __init__(self):
        super().__init__("Aborted by user", 106)
