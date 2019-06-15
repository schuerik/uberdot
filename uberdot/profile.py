"""This module implements the superclass for all profiles.

|
"""

###############################################################################
#
# Copyright 2018 Erik Schulz
#
# This file is part of uberdot.
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
###############################################################################


import builtins
import os
import re
import shutil
from abc import abstractmethod
from uberdot import constants
from uberdot.dynamicfile import *
from uberdot.errors import CustomError
from uberdot.errors import GenerationError
from uberdot.errors import FatalError
from uberdot.utils import expandvars
from uberdot.utils import expanduser
from uberdot.utils import find_target
from uberdot.utils import get_dir_owner
from uberdot.utils import import_profile_class
from uberdot.utils import log_warning
from uberdot.utils import normpath
from uberdot.utils import walk_dotfiles


CUSTOM_BUILTINS = [
    "cd",
    "decrypt",
    "default",
    "extlink",
    "has_tag",
    "link",
    "links",
    "merge",
    "opt",
    "pipe",
    "rmtags",
    "subprof",
    "tags",
]
"""A list of custom builtins that the profiles will map its functions to before
executing ``generate()``.

This means that, if you want to use a class function in ``generate()`` without
the need to call it via ``self``, add the function name to this list.
"""



class Profile:
    """This class provides the "API" aka commands for creating links and stores
    the state of the set options and directory.

    Attributes:
        __old_builtins (dict): A backup of the overwritten builtins
        name (str): Identifier/Class name of the profile
        executed (bool): True, if a result was already generated
        options (dict): Stores options that will be set with ``opt()``
            as well as the tags. Equals ``constants.DEFAULTS`` if this a
            root profile.
        directory (str): The directory that the profile is using as current
            working directory. Equals ``constants.DIR_DEFAULT`` if this a root
            profile.
        parent (Profile): The parent profile. ``None`` if this a root profile.
        result (dict): The result of ``generate()``. Contains name, parent,
            generated links and the result of all subprofiles.
    """
    def __init__(self, options=None, directory=None, parent=None):
        """Constructor.

        Sets ``self.options`` to ``constants.DEFAULTS`` if options is ``None``.

        Sets ``self.directory`` to ``constants.DIR_DEFAULT`` if directory is
        ``None``.
        """
        if options is None:
            options = dict(constants.DEFAULTS)
        if not directory:
            directory = constants.DIR_DEFAULT
        self.__old_builtins = {}
        self.name = self.__class__.__name__
        self.executed = False
        self.builtins_overwritten = False
        self.options = options
        self.directory = directory
        self.parent = parent
        self.result = {
            "name": self.name,
            "parent": self.parent,
            "links": [],
            "profiles": []
        }

    def _make_read_opt(self, kwargs):
        """Create function that can lookup options but prefers options set for
        a concrete command.

        Args:
            kwargs (dict): kwargs of a command
        Returns:
            function: A function that looks up and returns the value for a key
            in kwargs. If the key is not in kwargs it uses ``self.options`` for
            look up.
        """
        def read_opt(opt_name):
            if opt_name in kwargs:
                return kwargs[opt_name]
            return self.options[opt_name]
        return read_opt

    def generator(self):
        """This is the wrapper for ``generate()``. It overwrites the builtins
        and maps it own commands to them. ``generate()`` must not be called
        without this wrapper.

        `Do NOT call this from within the same profile, only from outside!!`

        Returns:
            dict: The result dictionary ``self.result``
        """
        if self.executed:
            self._gen_err("A profile can be only generated " +
                           "one time to prevent side-effects!")
        self.executed = True
        self.__set_builtins()
        try:
            self.generate()
        except Exception as err:
            if isinstance(err, CustomError):
                raise
            msg = "An unkown error occured in your generate() function: "
            self._gen_err(msg + type(err).__name__ + ": " + str(err))
        self.__reset_builtins()
        return self.result

    def __set_builtins(self):
        """Maps functions from ``CUSTOM_BUILTINS`` to builtins, so commands
        don't need to be called using ``self`` everytime.
        """
        if self.builtins_overwritten:
            raise FatalError("Builtins are already overwritten")
        for item in CUSTOM_BUILTINS:
            if item in builtins.__dict__:
                self.__old_builtins[item] = builtins.__dict__[item]
            builtins.__dict__[item] = self.__getattribute__(item)
        self.builtins_overwritten = True

    def __reset_builtins(self):
        """Restores old Builtin mappings."""
        if not self.builtins_overwritten:
            raise FatalError("Builtins weren't overwritten yet")
        for key, val in self.__old_builtins.items():
            builtins.__dict__[key] = val
        self.builtins_overwritten = False

    @abstractmethod
    def generate(self):
        """Implemeted by users for actual link configuration.

        `Do NOT call this function without its wrapper` ``generator()``.
        """
        raise NotImplementedError

    def _gen_err(self, msg):
        """A wrapper to raise a GenerationError with the profilename."""
        raise GenerationError(self.name, msg)

    def find(self, target):
        """Find a dotfile in ``TARGET_DIR``. Depends on the current set tags.

        This can be overwritten to change the searching behaviour of a profile.
        Furthermore it can be used by the user to just find a dotfile whithout
        linking it directly. Eventhough, this is not a command at the moment so
        it need to be called with ``self.find()`` in ``generate()``.

        Args:
            target (str): A filename, without preceding tag
        Raises:
            GenerationError: More than one file was found
        Return:
            str: The full path of the file or ``None`` if no file was found
        """
        try:
            return find_target(target, self.options["tags"])
        except ValueError as err:
            self._gen_err(err)

    def decrypt(self, target):
        """Creates an ``EncryptedFile`` instance from a target, updates and
        returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            target(str/DynamicFile): The target file that will be used as
                source of the ``EncryptedFile``
        Returns:
            EncryptedFile: The dynamic file that holds the decrypted target
        """
        if isinstance(target, DynamicFile):
            encrypt = EncryptedFile(target.name)
            encrypt.add_source(target.getpath())
        else:
            encrypt = EncryptedFile(target)
            encrypt.add_source(self.find(target))
        encrypt.update()
        return encrypt

    def merge(self, name, targets):
        """Creates a ``SplittedFile`` instance from a list of targets, updates
        and returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            targets(list): The list of targets that will be used as
                source of the ``SplittedFile``
        Returns:
            SplittedFile: The dynamic file that holds the merged target
        """
        if len(targets) < 2:
            self._gen_err("merge() for '" + name + "' needs at least "
                          + "two dotfiles to merge")
        split = SplittedFile(name)
        for target in targets:
            if isinstance(target, DynamicFile):
                split.add_source(target.getpath())
            else:
                split.add_source(self.find(target))
        split.update()
        return split

    def pipe(self, target, shell_command):
        """Creates a ``FilteredFile`` instance from a target, updates and
        returns it.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            target(str/DynamicFile): The target file that will be used as
                source of the ``FilteredFile``
            shell_command (str): The shell command that the content of target
                will be piped into
        Returns:
            FilteredFile: The dynamic file that holds the output of the shell
            command
        """
        if isinstance(target, DynamicFile):
            filtered = FilteredFile(target.name, shell_command)
            filtered.add_source(target.getpath())
        else:
            filtered = FilteredFile(target, shell_command)
            filtered.add_source(self.find(target))
        filtered.update()
        return filtered

    def link(self, *targets, **kwargs):
        """Link one ore more targets with current options.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            *targets (list): One ore more targets that shall be linked. Targets
                can be just file names or any dynamic files.
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            GenerationError: One of the targets were not found
        """
        read_opt = self._make_read_opt(kwargs)
        for target in targets:
            if isinstance(target, DynamicFile):
                found_target = target.getpath()
                if "name" not in kwargs:
                    kwargs["name"] = target.name
            else:
                found_target = self.find(target)
            if found_target:
                self.__create_link_descriptor(found_target, **kwargs)
            elif not read_opt("optional"):
                msg = "There is no target that matches: '" + target + "'"
                self._gen_err(msg)

    def extlink(self, path, **kwargs):
        """Link any file specified by its absolute path.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            path (str): The path of the target
            **kwargs (dict): A set of options that will be overwritten just
                for this call
        """
        read_opt = self._make_read_opt(kwargs)
        path = expanduser(expandvars(path))
        if not os.path.isabs(path):
            log_warning("'path' should be specified as an absolut path" +
                        " for extlink(). Relative paths are not forbidden" +
                        " but can cause undesired side-effects.")
        if not read_opt("optional") or os.path.exists(path):
            self.__create_link_descriptor(os.path.abspath(path), **kwargs)

    def links(self, target_pattern, encrypted=False, **kwargs):
        """Calls ``link()`` for all targets matching a pattern.

        Furthermore it allows to ommit the ``replace_pattern`` in favor of the
        ``target_pattern`` and to decrypt matched files first.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            target_pattern (str): The regular expression that matches the file
                names
            encrypted (bool): True, if the targets shall be decrypted
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            GenerationError: No files or multiple file with the same name were
                found with this pattern
        """
        read_opt = self._make_read_opt(kwargs)
        target_list = []
        target_dir = {}

        # Use target_pattern as replace_pattern
        if read_opt("replace") and not read_opt("replace_pattern"):
            kwargs["replace_pattern"] = target_pattern

        # Find all files that match target_pattern and index
        # them by there name without tag
        for root, name in walk_dotfiles():
            tag, base = (None, os.path.basename(name))
            if "%" in base:
                tag, base = base.split("%", 1)
            if re.fullmatch(target_pattern, base) is not None:
                if base not in target_dir:
                    target_dir[base] = []
                target_dir[base].append((tag, os.path.join(root, name)))

        def choose_file(base, tags):
            # Go through set tags and take the first file that matches a tag
            for tmp_tag in self.options["tags"]:
                for item in tags:
                    if item[0] == tmp_tag:
                        target_list.append(item[1])
                        return
            # Look for files without tags
            no_tag = None
            for item in tags:
                if item[0] is None:
                    if no_tag is None:
                        no_tag = item
                    else:
                        msg = "There are two targets found with the same name:"
                        msg += " '" + base + "'\n  " + no_tag[1]
                        msg += "\n  " + item[1]
                        self._gen_err(msg)
            if no_tag is not None:
                target_list.append(no_tag[1])
        # Then choose wisely which files will be linked
        for base, tags in target_dir.items():
            choose_file(base, tags)

        # Now we have all targets and can create links for each one
        if not target_list and not read_opt("optional"):
            self._gen_err("No files found that would match the"
                           + " pattern: '" + target_pattern + "'")
        else:
            for target in target_list:
                if encrypted:
                    file_name = os.path.basename(target)
                    target = self.decrypt(file_name).getpath()
                    kwargs["name"] = file_name
                self.__create_link_descriptor(target, **kwargs)


    def __create_link_descriptor(self, target, directory="", **kwargs):
        """Creates an entry in ``result["links"]`` with current options and a
        given target.

        Furthermore lets you set the directory like ``cd()``.

        Args:
            target (str): Full path to target file
            directory (str): A path to change the cwd
            kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            GenerationError: One or more options were misused
        """
        read_opt = self._make_read_opt(kwargs)

        # Now generate the correct name for the symlink
        replace = read_opt("replace")
        if replace:  # When using regex pattern, name property is ignored
            replace_pattern = read_opt("replace_pattern")
            if replace_pattern:
                if read_opt("name"):
                    # Usually it makes no sense to set a name when "replace" is
                    # used, but commands might set this if they got an
                    # dynamicfile, because otherwise you would have to match
                    # against the hash too
                    base = read_opt("name")
                else:
                    base = os.path.basename(target)
                if "%" in base:
                    base = base.split("%", 1)[1]
                name = re.sub(replace_pattern, replace, base)
            else:
                msg = "You are trying to use 'replace', but no "
                msg += "'replace_pattern' was set."
                self._gen_err(msg)
        else:
            name = expandvars(read_opt("name"))
        # And prevent exceptions in os.symlink()
        if name and name[-1:] == "/":
            self._gen_err("name mustn't represent a directory")

        # Put together the path of the dir we create the link in
        if not directory:
            directory = self.directory  # Use the current dir
        else:
            directory = expandvars(directory)
            if directory[0] != '/':  # Path is realtive, join with current
                directory = os.path.join(self.directory, directory)
        directory = expandvars(directory)
        # Concat directory and name. The users $HOME needs to be set for this
        # when executing as root, otherwise ~ will be expanded to the home
        # directory of the root user (/root)
        name = expanduser(os.path.join(directory, name))

        # Add prefix an suffix to name
        base, ext = os.path.splitext(os.path.basename(name))
        if not base:
            # If base is empty it means that "name" was never set by the user,
            # so we fallback to use the target name (but without the tag)
            base, ext = os.path.splitext(
                os.path.basename(target.split("%", 1)[-1])
            )
        name = os.path.join(os.path.dirname(name), read_opt("prefix") +
                            base + read_opt("suffix") + ext)
        name = os.path.normpath(name)

        # Get user and group id of owner
        owner = read_opt("owner")
        if owner:
            # Check for the correct format of owner
            try:
                user, group = owner.split(":")
            except ValueError:
                msg = "The owner needs to be specified in the format"
                self._gen_err(msg + 'user:group')
            try:
                uid = shutil._get_uid(user)
            except LookupError:
                msg = "You want to set the owner of '" + name + "' to '" + user
                msg += "', but there is no such user on this system."
                self._gen_err(msg)
            try:
                gid = shutil._get_gid(group)
            except LookupError:
                msg = "You want to set the owner of '" + name + "' to '"
                msg += group + "', but there is no such group on this system."
                self._gen_err(msg)
        else:
            # if no owner was specified, we need to set it
            # to the owner of the dir
            uid, gid = get_dir_owner(name)

        # Finally create the result entry
        linkdescriptor = {}
        linkdescriptor["target"] = target
        linkdescriptor["name"] = name
        linkdescriptor["uid"] = uid
        linkdescriptor["gid"] = gid
        linkdescriptor["permission"] = read_opt("permission")
        self.result["links"].append(linkdescriptor)

    def cd(self, directory):
        """Sets ``self.directory``. Unix-like cd.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            directory (str): The path to switch to
        """
        self.directory = os.path.normpath(
            os.path.join(self.directory, expandvars(directory))
        )

    def default(self, *options):
        """Resets options back to defaults. If called without arguments,
        it resets all options and tags.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            *options (list): A list of options that will be reseted
        """
        self.cd(constants.DIR_DEFAULT)
        if not options:
            self.options = dict(constants.DEFAULTS)
        else:
            for item in options:
                self.options[item] = constants.DEFAULTS[item]

    def rmtags(self, *tags):
        """Removes a list of tags.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            tags (list): A list of tags that will be removed
        """
        for tag in tags:
            if self.has_tag(tag):
                self.options["tags"].remove(tag)

    def tags(self, *tags):
        """Adds a list of tags.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            tags (list): A list of tags that will be added
        """
        for tag in tags:
            if tag not in self.options["tags"]:
                self.options["tags"].append(tag)

    def has_tag(self, tag):
        """Returns true if a tag is set.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            tag (str): A tag that will be checked for
        Returns:
            bool: True, if tag is set
        """
        return tag in self.options["tags"]

    def opt(self, **kwargs):
        """Sets options permanently. Set options will be used in all future
        calls of commands and subprofiles.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            **kwargs: A set of options that will be set permanently
        Raises:
            GenerationError: One of to be set option does not exist
        """
        for key in kwargs:
            if key in constants.DEFAULTS:
                self.options[key] = kwargs[key]
            else:
                self._gen_err("There is no option called " + key)

    def subprof(self, *profilenames, **kwargs):
        """Executes a list of profiles by name.

        This function is a command. It can be called without the use of
        ``self`` within ``generate()``.

        Args:
            *profilenames(list): A list of profilenames that will be executed
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            GenerationError: Profile were executed in a cycly or recursively
        """
        def will_create_cycle(subp, profile=self):
            return (profile.parent is not None and
                    (profile.parent.name == subp or
                     will_create_cycle(subp, profile.parent)))
        for subprofile in profilenames:
            if subprofile == self.name:
                self._gen_err("Recursive profiles are forbidden!")
            else:
                if will_create_cycle(subprofile):
                    self._gen_err("Detected a cycle in your subprofiles!")
                # All checks passed and the profile was imported, we can go on
                # merge this profile's options with this function's options
                suboptions = {**self.options, **kwargs}
                # Create instance of subprofile with merged options
                # and current directory
                ProfileClass = import_profile_class(subprofile)
                profile = ProfileClass(suboptions, self.directory, self)
                # Generate profile and add it to this profile's
                # generation result
                self.result["profiles"].append(profile.generator())
