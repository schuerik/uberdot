"""This module implements the superclass for all profiles and contains globals
and the ``@commands``-Decorator.

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
from uberdot.utils import expandpath
from uberdot.utils import find_target
from uberdot.utils import get_dir_owner
from uberdot.utils import import_profile_class
from uberdot.utils import normpath
from uberdot.utils import walk_dotfiles


custom_builtins = []
"""A list of custom builtins that the profiles will map its functions to
before executing :func:`~Profile.generate()`.

To add a function here, just add the ``@command`` decorator to it.
"""


def command(func):
    """Adding this decorator to a function will make it available
    in :func:`generate()` as a builtin.

    Furthermore it adds some documentation to the function.

    Args:
        func (function): The function that will become a command
    """
    # Add function to custom builtins
    custom_builtins.append(func.__name__)

    # Add documentation to function
    docs = func.__doc__.split("\n\n")
    new_doc = docs[0]
    new_doc += "\n\n        .. note:: "
    new_doc += "This function is a command. It can be called "
    new_doc += "without the use of ``self`` within :func:`generate()`."
    for i in range(1, len(docs)):
        new_doc += "\n\n" + docs[i]
    func.__doc__ = new_doc

    # Return modified function
    return func


class Profile:
    """This class provides the "API" aka commands for creating links and stores
    the state of the set options and directory.

    Attributes:
        __old_builtins (dict): A backup of the overwritten builtins
        name (str): Identifier/Class name of the profile
        executed (bool): True, if a result was already generated
        options (dict): Stores options that will be set with :func:`opt()`
            as well as the tags. Equals :const:`constants.DEFAULTS` if this a
            root profile.
        directory (str): The directory that the profile is using as current
            working directory. Equals :const:`constants.DIR_DEFAULT` if this
            a root profile.
        parent (Profile): The parent profile. ``None`` if this a root profile.
        result (dict): The result of :func:`generate()`. Contains name, parent,
            generated links and the result of all subprofiles.
    """
    def __init__(self, options=None, directory=None, parent=None):
        """Constructor.

        Uses :const:`constants.DEFAULTS` as default for
        :attr:`self.options<Profile.options>` if ``options`` is ``None``.

        Uses :const:`constants.DIR_DEFAULT` as default for
        :attr:`self.directory<Profile.directory>` if ``directory`` is ``None``.
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

    def __setattr__(self, name, value):
        """Setter for :attr:`self.directory<Profile.directory>`.

        Makes sure that :attr:`self.directory<Profile.directory>` is always
        expanded and noramlized.
        """
        if name == "directory":
            if hasattr(self, name):
                value = os.path.join(self.directory, expandpath(value))
            else:
                value = normpath(value)
        super(Profile, self).__setattr__(name, value)

    def _make_read_opt(self, kwargs):
        """Creates a function that looks up options but prefers options of
        kwargs.

        Args:
            kwargs (dict): kwargs of a command
        Returns:
            function: A function that looks up and returns the value for a key
            in kwargs. If the key is not in kwargs it uses
            :attr:`self.options<Profile.options>` for look up.
        """
        def read_opt(opt_name):
            if opt_name in kwargs:
                return kwargs[opt_name]
            return self.options[opt_name]
        return read_opt

    def generator(self):
        """This is the wrapper for :func:`generate()`. It overwrites the
        builtins and maps it own commands to them. :func:`generate()` must not
        be called without this wrapper.

        .. warning:: Do NOT call this from within the same profile, only
            from outside!!

        Returns:
            dict: The result dictionary :attr:`self.result<Profile.result>`
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
        """Maps functions from :const:`custom_builtins` to builtins,
        so commands don't need to be called using ``self`` everytime.
        """
        if self.builtins_overwritten:
            raise FatalError("Builtins are already overwritten")
        for item in custom_builtins:
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

        .. warning:: Do NOT call this function without its wrapper
            :func:`generator()`.
        """
        raise NotImplementedError

    def _gen_err(self, msg):
        """A wrapper to raise a :class:`~errors.GenerationError` with the
        profilename.
        """
        raise GenerationError(self.name, msg)

    @command
    def find(self, target):
        """Find a dotfile in :const:`~constants.TARGET_FILES`. Depends on the
        current set tags.

        This can be overwritten to change the searching behaviour of a profile.
        Furthermore it can be used by the user to just find a dotfile without
        linking it directly.

        Args:
            target (str): A filename, without preceding tag
        Raises:
            :class:`~errors.GenerationError`: More than one file was found
        Return:
            str: The full path of the file or ``None`` if no file was found
        """
        try:
            return find_target(target, self.options["tags"])
        except ValueError as err:
            self._gen_err(err)

    @command
    def decrypt(self, target):
        """Creates an :class:`~dynamicfile.EncryptedFile` instance from a
        target, updates and returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        Args:
            target(str/:class:`~dynamicfile.DynamicFile`): The target file that
                will be used as source of the
                :class:`~dynamicfile.EncryptedFile`
        Returns:
            :class:`~dynamicfile.EncryptedFile`: The dynamic file that holds
            the decrypted target
        """
        if isinstance(target, DynamicFile):
            encrypt = EncryptedFile(target.name)
            encrypt.add_source(target.getpath())
        else:
            encrypt = EncryptedFile(target)
            encrypt.add_source(self.find(target))
        encrypt.update()
        return encrypt

    @command
    def merge(self, name, targets):
        """Creates a :class:`~dynamicfile.SplittedFile` instance from a list of
        targets, updates and returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        Args:
            targets(list): The list of targets that will be used as
                source of the :class:`~dynamicfile.SplittedFile`
        Returns:
            :class:`~dynamicfile.SplittedFile`: The dynamic file that holds the
            merged target
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

    @command
    def pipe(self, target, shell_command):
        """Creates a :class:`~dynamicfile.FilteredFile` instance from a target,
        updates and returns it.

        Args:
            target(str/:class:`~dynamicfile.DynamicFile`): The target file that
                will be used as source of the
                :class:`~dynamicfile.FilteredFile`
            shell_command (str): The shell command that the content of target
                will be piped into
        Returns:
          :class:`~dynamicfile.FilteredFile`: The dynamic file that holds the
          output of the shell command
        """
        if isinstance(target, DynamicFile):
            filtered = FilteredFile(target.name, shell_command)
            filtered.add_source(target.getpath())
        else:
            filtered = FilteredFile(target, shell_command)
            filtered.add_source(self.find(target))
        filtered.update()
        return filtered

    @command
    def link(self, *targets, **kwargs):
        """Link one ore more targets with current options.

        Args:
            *targets (list): One ore more targets that shall be linked. Targets
                can be just file names or any dynamic files.
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: One of the targets were not found
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

    @command
    def extlink(self, path, **kwargs):
        """Link any file specified by its absolute path.

        Args:
            path (str): The path of the target
            **kwargs (dict): A set of options that will be overwritten just
                for this call
        """
        read_opt = self._make_read_opt(kwargs)
        path = os.path.join(self.directory, expandpath(path))
        if not read_opt("optional") or os.path.exists(path):
            self.__create_link_descriptor(path, **kwargs)
        self._gen_err("Target path '" + path +
                      "' does not exist on your filesystem!")

    @command
    def links(self, target_pattern, encrypted=False, **kwargs):
        """Calls :func:`link()` for all targets matching a pattern.

        Furthermore it allows to ommit the ``replace_pattern`` in favor of the
        ``target_pattern`` and to decrypt matched files first.

        Args:
            target_pattern (str): The regular expression that matches the file
                names
            encrypted (bool): True, if the targets shall be decrypted
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: No files or multiple file with
                the same name were found with this pattern
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
            if constants.TAG_SEPARATOR in base:
                tag, base = base.split(constants.TAG_SEPARATOR, 1)
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
        """Creates an entry in ``self.result["links"]`` with current options
        and a given target.

        Furthermore lets you set the directory like :func:`cd()`.

        Args:
            target (str): Full path to target file
            directory (str): A path to change the cwd
            kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: One or more options were misused
        """
        read_opt = self._make_read_opt(kwargs)

        # First generate the correct name for the symlink
        replace = read_opt("replace")
        name = read_opt("name")
        if replace:  # When using regex pattern, name property is ignored
            replace_pattern = read_opt("replace_pattern")
            if not replace_pattern:
                msg = "You are trying to use 'replace', but no "
                msg += "'replace_pattern' was set."
                self._gen_err(msg)
            if name:
                # Usually it makes no sense to set a name when "replace" is
                # used, but commands might set this if they got an
                # dynamicfile, because otherwise you would have to match
                # against the hash too
                base = name
            else:
                base = os.path.basename(target)
            if constants.TAG_SEPARATOR in base:
                base = base.split(constants.TAG_SEPARATOR, 1)[1]
            name = re.sub(replace_pattern, replace, base)
        elif name:
            name = expandpath(name)
            # And prevent exceptions in os.symlink()
            if name[-1:] == "/":
                self._gen_err("name mustn't represent a directory")
        else:
            # "name" wasn't set by the user,
            # so fallback to use the target name (but without the tag)
            name = os.path.basename(
                target.split(constants.TAG_SEPARATOR, 1)[-1]
            )

        # Add prefix an suffix to name
        base, ext = os.path.splitext(os.path.basename(name))
        name = os.path.join(os.path.dirname(name), read_opt("prefix") +
                            base + read_opt("suffix") + ext)
        name = os.path.normpath(name)

        # Put together the path of the dir we create the link in
        if not directory:
            directory = self.directory  # Use the current dir
        else:
            directory = os.path.join(self.directory, expandpath(directory))
        # Concat directory and name. The users $HOME needs to be set for this
        # when executing as root, otherwise ~ will be expanded to the home
        # directory of the root user (/root)
        name = expandpath(os.path.join(directory, name))

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

    @command
    def cd(self, directory):
        """Sets :attr:`self.directory<Profile.directory>`. Unix-like cd.

        The ``directory`` can be an absolute or relative path and it expands
        environment variables.

        Args:
            directory (str): The path to switch to
        """
        self.directory = directory

    @command
    def default(self, *options):
        """Resets :attr:`self.options<Profile.options>` back to
        :const:`constants.DEFAULTS`. If called without arguments,
        it resets all options and tags.

        Args:
            *options (list): A list of options that will be reset
        """
        self.cd(constants.DIR_DEFAULT)
        if not options:
            self.options = dict(constants.DEFAULTS)
        else:
            for item in options:
                self.options[item] = constants.DEFAULTS[item]

    @command
    def rmtags(self, *tags):
        """Removes a list of tags.

        Args:
            tags (list): A list of tags that will be removed
        """
        for tag in tags:
            if self.has_tag(tag):
                self.options["tags"].remove(tag)

    @command
    def tags(self, *tags):
        """Adds a list of tags.

        Args:
            tags (list): A list of tags that will be added
        """
        for tag in tags:
            if tag not in self.options["tags"]:
                self.options["tags"].append(tag)

    @command
    def has_tag(self, tag):
        """Returns true if a tag is set.

        Args:
            tag (str): A tag that will be checked for
        Returns:
            bool: True, if tag is set
        """
        return tag in self.options["tags"]

    @command
    def opt(self, **kwargs):
        """Sets options permanently. The set options will be used in all future
        calls of commands and subprofiles as long as the commands don't
        override them temporarily.

        Args:
            **kwargs: A set of options that will be set permanently
        Raises:
            :class:`~errors.GenerationError`: One of to be set option does
                not exist
        """
        for key in kwargs:
            if key in constants.DEFAULTS:
                self.options[key] = kwargs[key]
            else:
                self._gen_err("There is no option called " + key)

    @command
    def subprof(self, *profilenames, **kwargs):
        """Executes a list of profiles by name.

        Args:
            *profilenames(list): A list of profilenames that will be executed
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: Profile were executed in a
                cycly or recursively
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
