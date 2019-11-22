"""
This module contains all the different DynamicFiles and their base class.
DynamicFiles provide mechanisms to transform or manipulate dotfiles before
actually linking them. The DynamicFile will generate a new file that will
be linked instead and makes sure that user-made changes are preserved.

.. autosummary::
    :nosignatures:

    DynamicFile
    EncryptedFile
    FilteredFile
    SplittedFile
"""

###############################################################################
#
# Copyright 2018 Erik Schulz
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


import hashlib
import logging
import os
from abc import abstractmethod
from shutil import copyfile
from subprocess import PIPE
from subprocess import Popen
from uberdot import constants
from uberdot.utils import normpath


logger = logging.getLogger("root")


class DynamicFile:
    """The abstract base class for any dynamic generated file.
    It provides the update functionality and some basic information.

    Attributes:
        name (str): Name of the file
        md5sum (str): A checksum of the contents of the file
        sources (list): A list of paths of files that are used as source to
            generate the dynmaic file
    """
    def __init__(self, name):
        """Constructor

        Args:
            name (str): Name of the file
        """
        self.name = name
        self.md5sum = None
        self.sources = []

    @property
    @abstractmethod
    def SUBDIR(self):
        """This constant needs to be implemented by subclasses. It tells the
        DynamicFile where to store the generated content of the file. It should
        be different for every type of DynamicFile, so the user can find them
        easier and can view different "stages" of the generation if the
        DynamicFile was nested."""
        raise NotImplementedError

    @abstractmethod
    def _generate_file(self):
        """This abstract method is used to generate the contents of the
        DynamicFile from sources.

        Returns:
            bytearray: The raw generated content
        """
        pass

    def add_source(self, target):
        """Adds a source path and normalizes it.

        Args:
            target (str): A path to a file that will be used as source
        """
        self.sources.append(normpath(target))

    def update(self):
        """Generates the newest version of the file and writes it
        if it is not in its subdir yet."""
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

    def getpath(self):
        """Gets the path of the generated file

        Returns:
            str: The full path to the generated file
        """
        # Dynamicfiles are stored with its md5sum in the name to detect chages
        return os.path.join(self.getdir(),
                            self.name + constants.HASH_SEPARATOR + self.md5sum)

    def getdir(self):
        """Gets the path of the directory that is used to store the generated
        file.

        Returns:
            str: The path to the directory
        """
        path = normpath(os.path.join(constants.DATA_DIR, self.SUBDIR))
        if not os.path.isdir(path):
            os.mkdir(path)  # Create dir if it doesn't exist
        return path


class EncryptedFile(DynamicFile):
    """This implementation of a dynamic files allows to decrypt
    encrypted files.
    """

    SUBDIR = "decrypted"
    """Subdirectory used by EncryptedFile"""

    def _generate_file(self):
        """Decrypts the first file in :attr:`self.sources<dyanmicfile.sources>`
        using gpg.

        Returns:
            bytearray: The content of the decrypted file
        """
        # Get sources and temp file
        encryped_file = self.sources[0]
        tmp = os.path.join(self.getdir(), self.name)
        # Set arguments for OpenPGP
        args = ["gpg", "-q", "-d", "--yes"]
        if constants.DECRYPT_PWD:
            args += ["--batch", "--passphrase", constants.DECRYPT_PWD]
        else:
            logger.info("Tipp: You can set a password in uberdots " +
                        "config that will be used for all encrypted files.")
        args += ["-o", tmp, encryped_file]
        # Use OpenPGP to decrypt the file
        process = Popen(args, stdin=PIPE)
        process.communicate()
        # Remove the decrypted file. It will be written by the update function
        # of the super class to its correct location.
        result = open(tmp, "rb").read()
        os.remove(tmp)
        return result


class FilteredFile(DynamicFile):
    """This is implementation of a dynamic files allows to run a
    shell command on a dotfile before linking.
    """

    SUBDIR = "piped"
    """Subdirectory used by FilteredFile"""

    def __init__(self, name, shell_command):
        """Constructor.

        Args:
            name (str): Name of the file
            shell_command (str): A shell command that the file will be piped
                into
        """
        super().__init__(name)
        self.shell_command = shell_command

    def _generate_file(self):
        """Pipes the content of the first file in
        :attr:`self.sources<dyanmicfile.sources>` into the specified
        shell comand.

        Returns:
            bytearray: The output of the shell command
        """
        command = "cat " + self.sources[0] + " | " + self.shell_command + ""
        process = Popen(command, stdout=PIPE, shell=True)
        result, _ = process.communicate()
        return result


class SplittedFile(DynamicFile):
    """This is of a dynamic files allows to join multiple dotfiles
    together to one dotfile.
    """

    SUBDIR = "merged"
    """Subdirectory used by SplittedFile"""

    def _generate_file(self):
        """Merges all files from ``:class:`~interpreters.self`.sources``
        in order.

        Returns:
            bytearray: The content of all files merged together
        """
        result = bytearray()
        for file in self.sources:
            result.extend(open(file, "rb").read())
        return result
