""" This module implements the superclass for all profiles"""

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


import builtins
import os
import re
import shutil
from abc import abstractmethod
from typing import Any
from typing import Callable
from typing import List
from typing import NoReturn
from typing import Tuple
from typing import Union
from dotmanager import constants
from dotmanager.customtypes import Options
from dotmanager.customtypes import Path
from dotmanager.customtypes import Pattern
from dotmanager.customtypes import ProfileResult
from dotmanager.customtypes import RelPath
from dotmanager.dynamicfile import *
from dotmanager.errors import CustomError
from dotmanager.errors import GenerationError
from dotmanager.utils import expandvars
from dotmanager.utils import expanduser
from dotmanager.utils import find_target
from dotmanager.utils import get_dir_owner
from dotmanager.utils import import_profile_class
from dotmanager.utils import log_warning
from dotmanager.utils import normpath
from dotmanager.utils import walk_dotfiles

# The custom builtins that the profiles will implement
CUSTOM_BUILTINS = ["links", "link", "cd", "opt", "extlink", "has_tag", "merge",
                   "default", "subprof", "tags", "rmtags", "decrypt", "pipe"]


class Profile:
    """This class provides the "API" for creating links.
    It is also responsible for running a profile"""
    def __init__(self, options: Options = None,
                 directory: Path = None,
                 parent: "Profile" = None):
        if options is None:
            options = dict(constants.DEFAULTS)
        if not directory:
            directory = constants.DIR_DEFAULT
        self.name = self.__class__.__name__
        self.__execution_counter = 0
        self.options = options
        self.directory = directory
        self.__old_builtins = {}
        self.parent = parent
        self.result = {
            "name": self.name,
            "parent": self.parent,
            "links": [],
            "profiles": []
        }

    def __make_read_opt(self, kwargs: Options) -> Callable[[str], Any]:
        """Create function that can lookup variables set in the profiles"""
        def read_opt(opt_name: str) -> Any:
            if opt_name in kwargs:
                return kwargs[opt_name]
            return self.options[opt_name]
        return read_opt

    def get(self) -> ProfileResult:
        """Creates a list of all links for this profile and all
        subprofiles by calling generate()
        DON'T use this from within a profile, only from outside!!"""
        if self.__execution_counter > 0:
            self.__raise_generation_error("A profile can be only generated " +
                                          "one time to prevent side-effects!")
        self.__execution_counter += 1
        self.__set_builtins()
        try:
            self.generate()
        except Exception as err:
            if isinstance(err, CustomError):
                raise
            else:
                msg = "An unkown error occured in your generate() function: "
                self.__raise_generation_error(msg + type(err).__name__ +
                                              ": " + str(err))
        self.__reset_builtins()
        return self.result

    def __set_builtins(self) -> None:
        """Maps functions from self to builtins, so profiles don't
        need to use "self" everytime"""
        for item in CUSTOM_BUILTINS:
            if item in builtins.__dict__:
                self.__old_builtins[item] = builtins.__dict__[item]
            builtins.__dict__[item] = self.__getattribute__(item)

    def __reset_builtins(self) -> None:
        """Restores old Builtin mappings"""
        for key, val in self.__old_builtins.items():
            builtins.__dict__[key] = val

    @abstractmethod
    def generate(self) -> None:
        """Used by profiles for actual link configuration"""
        pass

    def __raise_generation_error(self, msg: str) -> NoReturn:
        """Raise a GenerationError with the profilename"""
        raise GenerationError(self.name, msg)

    def find(self, target: str) -> Path:
        """Find a dotfile in the repository. Depends on the current set tags"""
        try:
            return find_target(target, self.options["tags"])
        except ValueError as err:
            self.__raise_generation_error(err)

    def decrypt(self, target: Union[str, DynamicFile]) -> EncryptedFile:
        """Creates an EncryptedFile instance, updates and returns it"""
        if isinstance(target, DynamicFile):
            encrypt = EncryptedFile(target.name)
            encrypt.add_source(target.getpath())
        else:
            encrypt = EncryptedFile(target)
            encrypt.add_source(self.find(target))
        encrypt.update()
        return encrypt

    def merge(self, name: str,
              targets: List[Union[DynamicFile, str]]) -> SplittedFile:
        """Creates a SplittedFile instance, updates and returns it"""
        if len(targets) < 2:
            msg = f"merge() for '{name}' needs at least two dotfiles to merge"
            self.__raise_generation_error(msg)
        split = SplittedFile(name)
        for target in targets:
            if isinstance(target, DynamicFile):
                split.add_source(target.getpath())
            else:
                split.add_source(self.find(target))
        split.update()
        return split

    def pipe(self, target: Union[str, DynamicFile],
             shell_command: str) -> FilteredFile:
        """Creates a FilteredFile instance, updates and returns it"""
        if isinstance(target, DynamicFile):
            filtered = FilteredFile(target.name, shell_command)
            filtered.add_source(target.getpath())
        else:
            filtered = FilteredFile(target, shell_command)
            filtered.add_source(self.find(target))
        filtered.update()
        return filtered

    def link(self, *targets: List[Union[DynamicFile, str]],
             **kwargs: Options) -> None:
        """Link a specific target with current options"""
        read_opt = self.__make_read_opt(kwargs)
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
                self.__raise_generation_error(msg)

    def extlink(self, path: RelPath, **kwargs: Options) -> None:
        """Link any file specified by its absolute path"""
        read_opt = self.__make_read_opt(kwargs)
        path = expanduser(expandvars(path))
        if not os.path.isabs(path):
            log_warning("'path' should be specified as an absolut path" +
                        " for extlink(). Relative paths are not forbidden" +
                        " but can cause undesired side-effects.")
        if not read_opt("optional") or os.path.exists(path):
            self.__create_link_descriptor(os.path.abspath(path), **kwargs)

    def links(self, target_pattern: Pattern,
              encrypted: bool = False, **kwargs: Options) -> None:
        """Calls link() for all targets matching a pattern. Also allows you
        to ommit the 'replace_pattern' and use the target_pattern instead"""
        read_opt = self.__make_read_opt(kwargs)
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

        def choose_file(base: str, tags: Tuple[str, Path]) -> None:
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
                        self.__raise_generation_error(msg)
            if no_tag is not None:
                target_list.append(no_tag[1])
        # Then choose wisely which files will be linked
        for base, tags in target_dir.items():
            choose_file(base, tags)

        # Now we have all targets and can create links for each one
        if not target_list and not read_opt("optional"):
            msg = "No files found that would match the"
            msg += " pattern: '" + target_pattern + "'"
            self.__raise_generation_error(msg)
        else:
            for target in target_list:
                if encrypted:
                    file_name = os.path.basename(target)
                    target = self.decrypt(file_name).getpath()
                    kwargs["name"] = file_name
                self.__create_link_descriptor(target, **kwargs)


    def __create_link_descriptor(self, target: Path,
                                 directory: RelPath = "",
                                 **kwargs: Options) -> None:
        """Creates a link entry for current options and a given target.
        Also lets you set the dir like cd or options
        temporarily only for a link"""
        read_opt = self.__make_read_opt(kwargs)

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
                self.__raise_generation_error(msg)
        else:
            name = expandvars(read_opt("name"))
        # And prevent exceptions in os.symlink()
        if name and name[-1:] == "/":
            self.__raise_generation_error("name mustn't represent a directory")

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
                self.__raise_generation_error(msg + 'user:group')
            try:
                uid = shutil._get_uid(user)
            except LookupError:
                msg = "You want to set the owner of '" + name + "' to '" + user
                msg += "', but there is no such user on this system."
                self.__raise_generation_error(msg)
            try:
                gid = shutil._get_gid(group)
            except LookupError:
                msg = "You want to set the owner of '" + name + "' to '"
                msg += group + "', but there is no such group on this system."
                self.__raise_generation_error(msg)
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

    def cd(self, directory: RelPath) -> None:
        """Switches the directory where links should be created.
        Unix-like cd."""
        self.directory = os.path.normpath(
            os.path.join(self.directory, expandvars(directory))
        )

    def default(self, *options: List[str]) -> None:
        """Resets options back to defaults"""
        self.cd(constants.DIR_DEFAULT)
        if not options:
            self.options = dict(constants.DEFAULTS)
        else:
            for item in options:
                self.options[item] = constants.DEFAULTS[item]

    def rmtags(self, *tags: List[str]) -> None:
        """Remove a list of tags"""
        for tag in tags:
            if self.has_tag(tag):
                self.options["tags"].remove(tag)

    def tags(self, *tags: List[str]) -> None:
        """Add a list of tags"""
        for tag in tags:
            if tag not in self.options["tags"]:
                self.options["tags"].append(tag)

    def has_tag(self, tag: str) -> bool:
        """Returns true if tag is set"""
        return tag in self.options["tags"]

    def opt(self, **kwargs: Options) -> None:
        """Sets options for every next link or subprofile"""
        for key in kwargs:
            if key in constants.DEFAULTS:
                self.options[key] = kwargs[key]
            else:
                self.__raise_generation_error("There is no option called " +
                                              key)

    def subprof(self, *profilenames: List[str], **kwargs: Options) -> None:
        """Executes another profile by name"""
        def will_create_cycle(subp: str, profile: Profile = self) -> bool:
            return (profile.parent is not None and
                    (profile.parent.name == subp or
                     will_create_cycle(subp, profile.parent)))
        for subprofile in profilenames:
            if subprofile == self.name:
                self.__raise_generation_error("Recursive profiles are " +
                                              "forbidden")
            else:
                if will_create_cycle(subprofile):
                    self.__raise_generation_error("Detected a cycle in" +
                                                  " your subprofiles!")
                # All checks passed and the profile was imported, we can go on
                # merge this profile's options with this function's options
                suboptions = {**self.options, **kwargs}
                # Create instance of subprofile with merged options
                # and current directory
                ProfileClass = import_profile_class(subprofile)
                profile = ProfileClass(suboptions, self.directory, self)
                # Generate profile and add it to this profile's
                # generation result
                self.result["profiles"].append(profile.get())
