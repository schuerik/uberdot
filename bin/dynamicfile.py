import hashlib
import os
from abc import abstractmethod
from typing import List
from typing import Optional
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
        if not self.sources and tags is not None:
            self._find_sources(tags)
        file_bytes = self._generate_file()
        self.md5sum = hashlib.md5(file_bytes).hexdigest()
        if not os.path.isfile(self.getpath()):
            file = open(self.getpath(), "w")
            file.write(file_bytes)

    def getpath(self) -> Path:
        """Returns the path of the generated file"""
        name = self.name + "#" + self.md5sum
        return normpath(os.path.join("data", self.SUBDIR, name))


class EncryptedFile(DynamicFile):
    SUBDIR = "decrypted"

    def __init__(self, name: str) -> None:
        super().__init__(name)

    def _generate_file(self) -> bytearray:
        encryped_file = self.sources[0]
        tmp = self.getpath()[:-33]
        subprocess.run(["gpg", "--decrypt", encryped_file, "-o", tmp])
        result = open(tmp, "r").read()
        os.remove(tmp)
        return result
