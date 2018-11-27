""" This module implements the superclass for all profiles"""

import builtins
import os
import re
import shutil
from abc import abstractmethod
from typing import Any
from typing import Callable
from typing import List
from typing import NoReturn
from typing import Optional
from typing import Tuple
from bin import constants
from bin.errors import CustomError
from bin.errors import FatalError
from bin.errors import GenerationError
from bin.types import Options
from bin.types import Path
from bin.types import Pattern
from bin.types import ProfileResult
from bin.types import RelPath
from bin.utils import expandvars
from bin.utils import expanduser
from bin.utils import get_user_env_var
from bin.utils import get_dir_owner
from bin.utils import import_profile_class
from bin.utils import print_warning

# The custom builtins that the profiles will implement
CUSTOM_BUILTINS = ["links", "link", "cd", "opt", "extlink",
                   "default", "subprof", "tags", "rmtags"]


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

    def __find_target(self, target: str, tags: List[str]) -> Optional[Path]:
        """Find the correct target version in the repository to link to"""
        targets = []
        # Collect all files that have the same filename as the target
        for root, _, files in os.walk(constants.TARGET_FILES):
            for name in files:
                # We need to look if filename matches a tag
                for tag in tags:
                    if name == tag + "%" + target:
                        targets.append(os.path.join(root, name))
        if not targets:
            # Seems like nothing was found, but we searched only files
            # with tags so far. Trying without tags as fallback
            return self.__find_exact_target(target)
        # Return found target. Because we found files with tags, we use
        # the file that matches the earliest defined tag
        for tag in tags:
            for tmp_target in targets:
                if os.path.basename(tmp_target).startswith(tag):
                    return tmp_target
        raise FatalError("No target was found even though there seems to " +
                         "exist one. That's strange...")

    def __find_exact_target(self, target: str) -> Optional[Path]:
        """Find the exact target in the repository to link to"""
        targets = []
        # Collect all files that have the same filename as the target
        for root, _, files in os.walk(constants.TARGET_FILES):
            for name in files:
                if name == target:
                    targets.append(os.path.join(root, name))
        # Whithout tags there shall be only one file that matches the target
        if len(targets) > 1:
            msg = "There are multiple targets that match: '" + target + "'"
            for tmp_target in targets:
                msg += "\n  " + tmp_target
            self.__raise_generation_error(msg)
        elif not targets:
            # Ooh, nothing found
            return None
        # Return found target
        return targets[0]

    def link(self, *targets: List[str], **kwargs: Options) -> None:
        """Link a specific target with current options"""
        read_opt = self.__make_read_opt(kwargs)
        for target in targets:
            found_target = self.__find_target(target, read_opt("tags"))
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
            print_warning("'path' should be specified as an absolut path" +
                          " for extlink(). Relative paths are not forbidden" +
                          " but can cause undesired side-effects.")
        if not read_opt("optional") or os.path.exists(path):
            self.__create_link_descriptor(path, **kwargs)

    def links(self, target_pattern: Pattern, **kwargs: Options) -> None:
        """Calls link() for all targets matching a pattern. Also allows you
        to ommit the 'replace_pattern' and use the target_pattern instead"""
        read_opt = self.__make_read_opt(kwargs)
        target_list = []
        target_dir = {}

        # Use target_pattern as replace_pattern
        if read_opt("replace") != "" and read_opt("replace_pattern") == "":
            kwargs["replace_pattern"] = target_pattern

        # Find all files that match target_pattern and index
        # them by there name without tag
        for root, _, files in os.walk(constants.TARGET_FILES):
            for file in files:
                tag, base = (None, os.path.basename(file))
                if "%" in base:
                    tag, base = base.split("%", 1)
                if re.fullmatch(target_pattern, base) is not None:
                    if base not in target_dir:
                        target_dir[base] = []
                    target_dir[base].append((tag, os.path.join(root, file)))

        def choose_file(base: str, tags: Tuple[str, Path]) -> None:
            # Go through set tags and take the first file that matches a tag
            for tmp_tag in read_opt("tags"):
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
                self.__create_link_descriptor(target, **kwargs)


    def __create_link_descriptor(self, target: RelPath,
                                 directory: RelPath = "",
                                 **kwargs: Options) -> None:
        """Creates a link entry for current options and a given target.
        Also lets you set the dir like cd or options
        temporarily only for a link"""
        read_opt = self.__make_read_opt(kwargs)

        # Prepare target
        target = expandvars(target)
        target = os.path.abspath(target)

        # Now generate the correct name for the symlink
        replace = read_opt("replace")
        if replace:  # When using regex pattern, name property is ignored
            if read_opt("name") != "":
                print_warning("'name'-property is useless if" +
                              " 'replace' is used")
            replace_pattern = read_opt("replace_pattern")
            if replace_pattern:
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
            if read_opt("preserve_tags"):
                base, ext = os.path.splitext(os.path.basename(target))
            else:
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
