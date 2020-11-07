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


import logging
import os
import sys
from abc import abstractmethod
from difflib import SequenceMatcher
from subprocess import PIPE
from subprocess import Popen
from uberdot.state import GenBuildupData, GenCopyData
from uberdot import utils

const = utils.Const()
log = utils.log
log_debug = utils.log_debug
log_warning = utils.log_warning


def getModuleAttr(name):
    return getattr(sys.modules[__name__], name)


def load_file_from_buildup(buildupdata):
    return getModuleAttr(buildupdata["type"]).load(buildupdata)


class AbstractFile:
    def __init__(self, name, md5sum=None, source=None, content=None, origin=None):
        """Base constructor. Do not use.

        This creates only a frame that can be empty, uninitalised or
        outdated. Use new() and load() to create proper instances.

        Args:
            name (str): Name of the file
        """
        self.name = name
        self.md5sum = md5sum
        self._content = content
        self._source = source
        self.origin = origin
        self.parent = None

    @classmethod
    def load(cls, buildupdata):
        """Creates a new instance from buildupdata

        Args:
            linkdata (AutoExpandDict): Info about the link
        """
        raise NotImplementedError

    @classmethod
    def new(cls, name, source=None, origin=None, **kwargs):
        if source is None:
            raise ValueError("source not set")
        if origin is None:
            raise ValueError("origin not set")
        obj = cls(name, source=source, **kwargs)
        obj.update_from_source()
        return obj

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        # First check the type of new source
        if source is None:
            raise UnsupportedError("source cannot be unset")
        self._check_source(source)
        # Set source and invoke update
        self._source = source
        self.update_from_source()

    def update_from_source(self):
        # Set new content and write to file
        self._content = self.forward_manipulation(self._get_src_content())
        self.write()
        # Recursive call propagates changes to parent
        if self.parent is not None:
            self.parent.update_from_source()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, content):
        self._content = content
        if content is not None:
            self.update_from_content()
            self.write()

    @abstractmethod
    def update_from_content(self):
        raise NotImplementedError

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
    def _get_src_content(self):
        raise NotImplementedError

    @abstractmethod
    def forward_manipulation(self, file_bytes):
        raise NotImplementedError

    @abstractmethod
    def backward_manipulation(self, file_bytes):
        raise NotImplementedError

    @abstractmethod
    def _check_source(self, source):
        raise NotImplementedError

    def getpath(self):
        """Gets the path of the generated file

        Returns:
            str: The full path to the generated file
        """
        # Dynamicfiles are stored with its md5sum in the name to detect chages
        if self.md5sum is None:
            raise ValueError("not updated")
        return os.path.join(
            self.getdir(),
            self.name + const.settings.hash_separator + self.md5sum
        )

    def getbackuppath(self):
        return self.getpath() + "." + const.settings.backup_extension

    def getdir(self):
        """Gets the path of the directory that is used to store the generated
        file.

        Returns:
            str: The path to the directory
        """
        path = os.path.join(const.internal.session_dir, "files", self.SUBDIR)
        utils.makedirs(path)
        return path

    def write(self):
        # Refresh md5sum, so we are writing to the correct file
        self.md5sum = utils.md5(self.content)
        # Check if this version of the file (with same checksum) already exists
        if not os.path.isfile(self.getpath()):
            log_debug("Writing " + type(self).__name__ + " to '" + self.getpath() + "'.")
            file = open(self.getpath(), "wb")
            file.write(self.content)
            file.flush()
            # Also create a backup that can be used to restore the original
            utils.create_backup(self.getpath())

    @abstractmethod
    def get_buildup_data(self):
        raise NotImplementedError

    def __repr__(self):
        str_ = self.__class__.__name__ +  "("
        str_ += ", ".join([self.name, self.md5sum, repr(self.source)])
        str_ += ")"
        return str_


class DynamicFile(AbstractFile):
    @classmethod
    def load(cls, buildupdata):
        path = buildupdata["path"]
        basename = os.path.basename(path)
        name, md5sum = basename.split(const.settings.hash_separator)
        source = getModuleAttr(buildupdata["source"]["type"]).load(buildupdata["source"])
        return cls(name, md5sum=md5sum, source=source, origin=buildupdata.origin)

    def _check_source(self, source):
        if not isinstance(source, AbstractFile):
            msg = "source must be an instance of AbstractFile, not "
            msg += type(source).__name__
            raise TypeError(msg)

    def update_from_content(self):
        file_bytes = self.backward_manipulation(self.content)
        checksum = utils.md5(file_bytes)
        # Recursive call
        if self.source.md5sum != checksum:
            self.source.content = file_bytes

    def _get_src_content(self):
        return self.source.content

    def get_buildup_data(self):
        return GenBuildupData(
            {
                "path": self.getpath(),
                "type": self.__class__.__name__,
                "source": self.source.get_buildup_data()
            }
        )


class MultipleSourceDynamicFile(AbstractFile):
    """The abstract base class for any dynamic generated file.
    It provides the update functionality and some basic information.

    Attributes:
        name (str): Name of the file
        md5sum (str): A checksum of the contents of the file
        sources (list): A list of dynamic files that are used as source to
            generate the new dynamic file
    """
    @classmethod
    def load(cls, buildupdata):
        path = buildupdata["path"]
        basename = os.path.basename(path)
        name, md5sum = basename.split(const.settings.hash_separator)
        source = []
        for src in buildupdata["source"]:
            source.append(
                getModuleAttr(src["type"]).load(src)
            )
        return cls(name, md5sum=md5sum, source=source, origin=buildupdata.origin)

    def _get_src_content(self):
        return [x.content for x in self.source]

    def update_from_content(self):
        files_bytes = self.backward_manipulation(self.content)
        for i, file_bytes in enumerate(files_bytes):
            checksum = utils.md5(file_bytes)
            # Recursive call
            if self.source[i].md5sum != checksum:
                self.source[i].content = file_bytes
        self.write()

    def _check_source(self, source):
        if not isinstance(source, list):
            msg = "source must be a list, not " + type(source).__name__
            raise TypeError(msg)
        for src in source:
            if not isinstance(src, AbstractFile):
                msg = "sources contains an object that is not instance of"
                msg += "AbstractFile, but " + type(src).__name__
                raise TypeError(msg)

    def get_buildup_data(self):
        return GenBuildupData(
            {
                "path": self.getpath(),
                "type": self.__class__.__name__,
                "source": [src.get_buildup_data() for src in self.source]
            }
        )


class StaticFile(AbstractFile):
    """This implementation of a dynamic files is used to store static
    copies of the original target files.
    """

    SUBDIR = "static"
    """Subdirectory used by StaticFile"""

    @classmethod
    def load(cls, buildupdata):
        path = buildupdata["path"]
        basename = os.path.basename(path)
        name, md5sum = basename.split(const.settings.hash_separator)
        return cls(name, md5sum=md5sum, source=buildupdata["source"], origin=buildupdata.origin)

    def update_from_content(self):
        def write_source():
            log_debug("Writing content of StaticFile back to '" + self.source + "'.")
            utils.create_tmp_backup(self.source)
            open(self.source, "wb").write(self.content)
            utils.remove_tmp_backup(self.source)

        def select_action(action):
            file = self.getpath()
            file_bak = self.getbackuppath()
            if action == "i":
                return True
            if action == "s":
                # Create a colored diff between the original and the source
                process = Popen(["diff", "--color=auto", file_bak, self.source])
                process.communicate()
                return False
            if action == "w":
                write_source()
                return True
            if action == "p":
                if not info.pkg_installed("git"):
                    print("This option requires git installed.")
                    return False
                # Create a git patch with git diff
                patch_file = os.path.splitext(self.source)[0] + ".patch"
                patch_file = user_selection("Enter filename for patch", patch_file)
                patch_file = abspath(patch_file, origin=const.internal.owd)
                args = ["git", "diff", "--no-index", file_bak, self.source]
                process = Popen(args, stdout=PIPE)
                try:
                    with open(patch_file, "wb") as pfile:
                        pfile.write(process.stdout.read())
                    log("Patch file written successfully to '" + patch_file + "'.")
                except OSError as err:
                    msg = "Could not write patch file '" + patch_file + "'. "
                    msg += str(err)
                    raise utils.PreconditionError(msg)
                action = "u"
            if action == "u":
                # Copy the original to the changed
                copyfile(file_bak, self.source)
                return True
            if action == "d":
                copyfile(file_bak, self.source)
                copyfile(file_bak, file)
                return True
            return False

        # Check for file changes
        source_hash = utils.md5(self._get_src_content())
        content_hash = utils.md5(self.content)
        # self.md5sum contains the hash of the old content at this point
        if self.md5sum == content_hash:
            # Content didn't change at all, so nothing to do. Don't even write it.
            return
        elif self.md5sum == source_hash:
            # Content did change, but the source didn't so we can simply
            # write it back
            write_source()
        elif content_hash == source_hash:
            # Content did change, but it was already propagated to source.
            # We still want to write it, so that it updates, but nothing else to do here.
            pass
        else:
            msg = "Conflict detected when writing file '" + self.name
            msg += "' back to its source '" + self.source
            msg += "' because the source contains changes."
            log_warning(msg)
            done = False
            raise ValueError
            # if const.settings.sync_action:
            #     done = select_action(const.settings.sync_action, source, source_bak)
            while not done:
                done = select_action(utils.user_choice(
                    ("I", "Ignore"), ("M", "Merge"),
                    ("s", "Show source diff"), ("W", "Write file anyway"),
                    ("p", "Create patch and use source"), ("U", "Use source"),
                    ("D", "Discard all changes"),
                    abort=True, short=True
                ))
        # Write file. This updates the md5sum as well.
        self.write()

    def _check_source(self, source):
        if not isinstance(source, str):
            raise TypeError("source needs to be of type string, not " + type(source).__name__)
        if not os.access(source, os.W_OK):
            raise utils.PreconditionError("No write permission for '" + source + "'.")

    def _get_src_content(self):
        """Returns the contents of the source file.

        Returns:
            bytearray: The raw file content
        """
        return open(self.source, "rb").read()

    def forward_manipulation(self, file_bytes):
        return file_bytes

    def backward_manipulation(self, file_bytes):
        return file_bytes

    def get_buildup_data(self):
        return GenCopyData(
            {
                "path": self.getpath(),
                "type": self.__class__.__name__,
                "source": self.source
            }
        )


class EncryptedFile(DynamicFile):
    """This implementation of a dynamic files allows to decrypt
    encrypted files.
    """

    SUBDIR = "decrypted"
    """Subdirectory used by EncryptedFile"""

    def __init__(self, name, **kwargs):
        if not info.pkg_installed("gpg"):
            raise PreconditionError("Using an EncryptedFile requires gnupg installed.")
        super().__init__(name, **kwargs)

    def forward_manipulation(self, file_bytes):
        """Decrypts the first file in :attr:`self.sources<dyanmicfile.sources>`
        using gpg.

        Returns:
            bytearray: The content of the decrypted file
        """
        return self._invoke_gnupg(file_bytes)

    def backward_manipulation(self, file_bytes):
        return self._invoke_gnupg(file_bytes, ["--symmetric"])

    def _create_gnupg_command(self, tmp_output, custom_args, censore_pwd=True):
        args = ["gpg", "-q", "--yes"] + custom_args
        if const.settings.decrypt_pwd:
            args += ["--batch", "--passphrase"]
            if censore_pwd:
                pwd = const.settings.decrypt_pwd
            else:
                pwd = const.settings.get("decrypt_pwd")._value
            args += [pwd]
        else:
            log("Tipp: You can set a password in uberdots " +
                "config that will be used for all encrypted files.")
        return args + ["-o", tmp_output]

    def _invoke_gnupg(self, input_content, custom_args=["-d"]):
        tmp_out = os.path.join(self.getdir(), self.name + ".tmp")
        # Set arguments for OpenPGP
        args = self._create_gnupg_command(tmp_out, custom_args, censore_pwd=False)
        strargs = " ".join(self._create_gnupg_command(tmp_out, custom_args))
        log_debug("Invoking OpenPGP with '" + strargs + "'")
        # Use OpenPGP to decrypt the file
        # TODO this is missing a try block
        process = Popen(args, stdin=PIPE, stderr=PIPE)
        _, stderr = process.communicate(input=input_content)
        if process.returncode:
            msg = "Invoking OpenPGP failed. Error output was:\n" + stderr.decode()
            raise utils.PreconditionError(msg)
        # Remove the decrypted file. It will be written by the update function
        # of the super class to its correct location.
        result = open(tmp_out, "rb").read()
        os.remove(tmp_out)
        return result


class FilteredFile(DynamicFile):
    """This is implementation of a dynamic files allows to run a
    shell command on a dotfile before linking.
    """

    SUBDIR = "piped"
    """Subdirectory used by FilteredFile"""

    def __init__(self, name, shell_command="", **kwargs):
        """Constructor.

        Args:
            name (str): Name of the file
            shell_command (str): A shell command that the file will be piped
                into
        """
        super().__init__(name, **kwargs)
        self.shell_command = shell_command

    def forward_manipulation(self, file_bytes):
        """Pipes the content of the first file in
        :attr:`self.sources<dyanmicfile.sources>` into the specified
        shell comand.

        Returns:
            bytearray: The output of the shell command
        """
        command = "cat | " + self.shell_command + ""
        log_debug("Piping file through shell command with '" + command + "'")
        process = Popen(command, stdin=PIPE, stdout=PIPE, shell=True)
        # TODO error handling
        result, _ = process.communicate(input=file_bytes)
        return result

    def backward_manipulation(self, file_bytes):
        # TODO: More info about the file that needs to be fixed manually
        raise UnsupportedError("FilteredFiles can not reverse its modifications. Fix it yourself.")


class SplittedFile(MultipleSourceDynamicFile):
    """This is of a dynamic files allows to join multiple dotfiles
    together to one dotfile.
    """

    SUBDIR = "merged"
    """Subdirectory used by SplittedFile"""

    def __init__(self, name, file_lengths=[], **kwargs):
        super().__init__(name, **kwargs)
        self.file_lengths = file_lengths

    @classmethod
    def load(cls, buildupdata):
        splittedfile = super(SplittedFile, cls).load(buildupdata)
        splittedfile.file_lengths = buildupdata["file_lengths"]
        return splittedfile

    def forward_manipulation(self, file_bytes):
        """Merges all files from ``:class:`~interpreters.self`.sources``
        in order.

        Returns:
            bytearray: The content of all files merged together
        """
        result = bytearray()
        self.file_lengths = []
        for fb in file_bytes:
            lines = fb.split(b"\n")
            linecount = len(lines) if lines[-1] else len(lines)-1
            self.file_lengths.append(linecount)
            result.extend(fb)
        return result

    def backward_manipulation(self, file_bytes):
        def increment_cursor(count):
            nonlocal cursor, file_idx
            if cursor + count > file_lengths[file_idx]:
                # Increment is bigger than current file size, so we need to go to the next file
                # First calculate how much to increment after we reached the end of the current file
                count = cursor + count - file_lengths[file_idx]
                # Then reset cursor and go to the next file
                cursor = 0
                file_idx += 1
                # Increment cursor for the next file with the remaining count
                increment_cursor(count)
            else:
                cursor += count
        # The backwards manipulation needs to figure out where to split
        # the file, so that the content is propagated to the correct source

        # current and previous will contain the current and previous content of the entire file
        current = file_bytes.decode()
        previous = "".join([open(file.getpath(), "r").read() for file in self.source])
        # index that takes track of which source file we are currently looking at
        file_idx = 0
        # index that takes track at which line in the current source file we are looking at
        cursor = 0
        # new file_lengths
        file_lengths = self.file_lengths[:]
        # Calculate diff betweeen previous and current. We will use the diff operations
        # to figure out, which change belongs to which source file
        seqm = SequenceMatcher(None, previous.split("\n"), current.split("\n"), False)
        for tag, i1, i2, j1, j2 in seqm.get_opcodes():
            # TODO: i can construct cases which will make this fail. eg if you delete
            # a hunk containing an entire source file, file_idx won't be incremented and
            # file_lengths will be wrong. Im sure there are more cases like this.
            linecount_old = i2-i1
            linecount_new = j2-j1
            if tag == "equal":
                increment_cursor(linecount_old)
            elif tag == "delete":
                file_lengths[file_idx] -= linecount_old
            elif tag == "insert":
                file_lengths[file_idx] += linecount_new
                increment_cursor(linecount_new)
            else:  # tag == "replace"
                file_lengths[file_idx] -= linecount_old
                file_lengths[file_idx] += linecount_new
                increment_cursor(linecount_new)
        # Create result for sources depending on the current content and the
        # new file_lengths
        used_lines = 0
        result = []
        for i, file in enumerate(self.source):
            result.append(current[used_lines:file_lengths[i]].encode())
            used_lines += file_lengths[i]
        return result

    def get_buildup_data(self):
        buildup = super().get_buildup_data()
        buildup["file_lengths"] = self.file_lengths
        return buildup
