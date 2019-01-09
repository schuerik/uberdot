"""
This module contains all the different DynamicFiles and their base class.
DynamicFiles provide mechanisms to transform or manipulate dotfiles before
actually linking them. The DynamicFile will generate a new dotfile that will
be linked instead and makes sure that user-made changes are preserved.
"""

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


import hashlib
import os
from abc import abstractmethod
from shutil import copyfile
from subprocess import PIPE
from subprocess import Popen
from typing import List
from bin import constants
from bin.errors import FatalError
from bin.types import Path
from bin.utils import normpath
from bin.utils import find_target


class DynamicFile:
    """This abstract class is the base for any dynamic generated
    file. It provides the write functionality and its path"""
    def __init__(self, name: str) -> None:
        self.name = name
        self.md5sum = None
        self.sources = []

    @property
    @abstractmethod
    def SUBDIR(self):
        """This constant needs to be implemented by subclasses"""
        raise NotImplementedError

    @abstractmethod
    def _generate_file(self) -> bytearray:
        """This method is used to generate the contents of the
        dynamic file from sources by returning it as bytearray"""
        pass

    def add_source(self, target) -> List[Path]:
        """This method is used to automatically find the sources to use."""
        self.sources.append(normpath(target))

    def update(self) -> None:
        """Gets the newest version of the file and writes it
        if it is not in its subdir yet"""
        # Generate file and calc checksum
        file_bytes = self._generate_file()
        self.md5sum = hashlib.md5(file_bytes).hexdigest()
        # If this version of the file (with same checksum) doesn't exist,
        # write it to the correct location
        if not os.path.isfile(self.getpath()):
            file = open(self.getpath(), "wb")
            file.write(file_bytes)
            file.flush()
            # Also create a backup that can be used to restore the original
            copyfile(self.getpath(),
                     self.getpath() + "." + constants.BACKUP_EXTENSION)

    def getpath(self) -> Path:
        """Returns the path of the generated file"""
        # Dynamicfiles are stored with its md5sum in the name to detect chages
        return os.path.join(self.getdir(), self.name + "#" + self.md5sum)

    def getdir(self) -> Path:
        """Returns the path of the directory that hold the generated file"""
        return normpath(os.path.join("data", self.SUBDIR))


class EncryptedFile(DynamicFile):
    """This is an implementation of a dynamic files that allows
    to decrypt encrypted files and link them on the fly"""
    SUBDIR = "decrypted"

    def _generate_file(self) -> bytearray:
        # Use OpenPGP to decrypt the file
        # We never provided sources, so the file will be found by find_target
        encryped_file = self.sources[0]
        tmp = os.path.join(self.getdir(), self.name)
        args = ["gpg", "-q", "-d", "--yes", "-o", tmp, encryped_file]
        process = Popen(args, stdin=PIPE)
        # Type in password
        if constants.DECRYPT_PWD:
            process.communicate(bytearray(constants.DECRYPT_PWD, "utf-8"))
        else:
            print("Tipp: You can set a password in the dotmanagers config" +
                  " that will be used for all encrypted files")
            process.communicate()
        # Remove the decrypted file. It will be written by the update function
        # of the super class to its correct location.
        result = open(tmp, "rb").read()
        os.remove(tmp)
        return result


class SplittedFile(DynamicFile):
    """This is an implementation of a dynamic files that allows
    to join multiple dotfiles together to one dotfile"""
    SUBDIR = "merged"

    def _generate_file(self) -> bytearray:
        result = bytearray()
        for file in self.sources:
            result.extend(open(file, "rb").read())
        return result
