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

    def _find_sources(self, tags: List[str]) -> List[Path]:
        """This method is used to automatically find the sources to use."""
        self.sources.append(find_target(self.name, tags))

    def update(self, tags: List[str] = None) -> None:
        """Gets the newest version of the file and writes it
        if it is not in its subdir yet"""
        if not self.sources:
            if tags is not None:
                self._find_sources(tags)
            else:
                raise FatalError("No sources are provided so tags must be set")
        file_bytes = self._generate_file()
        self.md5sum = hashlib.md5(file_bytes).hexdigest()
        if not os.path.isfile(self.getpath()):
            file = open(self.getpath(), "wb")
            file.write(file_bytes)
            file.flush()
            copyfile(self.getpath(),
                     self.getpath() + "." + constants.BACKUP_EXTENSION)

    def getpath(self) -> Path:
        """Returns the path of the generated file"""
        return os.path.join(self.getdir(), self.name + "#" + self.md5sum)

    def getdir(self) -> Path:
        """Returns the path of the directory that hold the generated file"""
        return normpath(os.path.join("data", self.SUBDIR))


class EncryptedFile(DynamicFile):
    """This is an implementation of a dynamic files that allows
    to decrypt encrypted files and link them on the fly"""
    SUBDIR = "decrypted"

    def _generate_file(self) -> bytearray:
        encryped_file = self.sources[0]
        tmp = os.path.join(self.getdir(), self.name)
        args = ["gpg", "-q", "-d", "--yes", "-o", tmp, encryped_file]
        process = Popen(args, stdin=PIPE)
        if constants.DECRYPT_PWD:
            process.communicate(bytearray(constants.DECRYPT_PWD, "utf-8"))
        else:
            print("Tipp: You can set a password in the dotmanagers config" +
                  " that will be used for all encrypted files")
            process.communicate()
        result = open(tmp, "rb").read()
        os.remove(tmp)
        return result
