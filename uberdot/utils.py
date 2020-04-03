
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


import datetime
import csv
from argparse import Namespace
import hashlib
import inspect
import grp
import importlib.util
import logging
import math
import os
import pwd
import re
import subprocess
import sys
import time
import configparser
from itertools import islice
from abc import abstractmethod


# Utils for finding targets
###############################################################################

class Walker:
    def __init__(self, path):
        self.iterator = os.walk(path)
        self.files = []
        self.root = None

    def __iter__(self):
        return self

    def __next__(self):
        while not self.files:
            self.root, _, self.files = next(self.iterator)
        result = self.files.pop()
        return self.root, result


class SafeWalker:
    def __init__(self, path, ignorelist, joined):
        self.iterator = walk(path)
        self.ignorelist = ignorelist + [
            r"/home/\w+/\.uberdot.*",
            r"/root/\.uberdot.*"
        ]
        self.joined = joined

    def __iter__(self):
        return self

    def __next__(self):
        get_next = True
        while get_next:
            get_next = False
            # Skip all internal files and symlinks
            result = next(self.iterator)
            file = os.path.join(result[0], result[1])
            for ignore_pattern in self.ignorelist:
                if re.fullmatch(ignore_pattern, file):
                    get_next = True
        if self.joined:
            return os.path.join(result[0], result[1])
        return result[0], result[1]

def walk(path):
    return iter(Walker(path))

def safe_walk(path, ignorelist=[], joined=False):
    return iter(SafeWalker(path, ignorelist, joined))

def find_target(target, tags):
    """Finds the correct target version in the repository to link to.

    This will search :const:`~constants.TARGET_FILES` for files that match the
    naming schema `<any string>%<target>` and returns the file whose
    `<any string>` occurs first in ``tags``. If no file is found the return
    value of :func:`find_exact_target()` is returned.

    Args:
        target (str): The filename that will be searched for
        tags (list): A list of tags that will be matched against the search
            result
    Raises:
        ValueError: Multiple targets where found
    Returns:
        str: Relative path of found file. Returns ``None`` if no target found.
    """
    targets = []
    # Collect all files that have the same filename as the target
    for root, name in walk_dotfiles():
        # We need to look if filename matches a tag
        for tag in tags:
            if name == tag + const.settings.tag_separator + target:
                targets.append(os.path.join(root, name))
    if not targets:
        # Seems like nothing was found, but we searched only files
        # with tags so far. Trying without tags as fallback
        return find_exact_target(target)
    # Return found target. Because we found files with tags, we use
    # the file that matches the earliest defined tag
    for tag in tags:
        for tmp_target in targets:
            if os.path.basename(tmp_target).startswith(tag):
                return tmp_target
    raise FatalError("No target was found even though there seems to " +
                     "exist one. That's strange...")


def find_exact_target(target):
    """Finds the exact target in the repository to link to.

    This will search :const:`~constants.TARGET_FILES` for files that match
    ``target``.

    Args:
        target (str): The filename that will be searched for
    Raises:
        :class:`~errors.ValueError`: Multiple targets where found
    Returns:
        str: Relative path of found file. Returns ``None`` if no target
        found.
    """
    targets = []
    # Collect all files that have the same filename as the target
    for root, name in walk_dotfiles():
        if name == target:
            targets.append(os.path.join(root, name))
    # Whithout tags there shall be only one file that matches the target
    if len(targets) > 1:
        msg = "There are multiple targets that match: '" + target + "'"
        for tmp_target in targets:
            msg += "\n  " + tmp_target
        raise ValueError(msg)
    if not targets:
        # Ooh, nothing found
        return None
    # Return found target
    return targets[0]


def walk_dotfiles():
    """Walks through the :const:`~constants.TARGET_FILES` and returns all files
    found.

    This also takes the .dotignore-file into account.

    Returns:
        (list): Contains tuples with the directory and the filename of every
        found file
    """
    # load ignore list
    ignorelist_path = os.path.join(const.settings.target_files, ".dotignore")
    ignorelist = []
    if os.path.exists(ignorelist_path):
        with open(ignorelist_path, "r") as file:
            ignorelist = file.readlines()
        ignorelist = [entry.strip() for entry in ignorelist if entry.strip()]
    ignorelist.append(r"\/.+\.dotignore$")

    return safe_walk(const.settings.target_files, ignorelist)


def walk_profiles():
    # Ignore all files that are no python files
    return safe_walk(const.settings.profile_files, [r".*[^p][^y]$"], joined=True)

def find_files(filename, paths):
    """Finds existing files matching a specific name in a list of paths.

    Args:
        filename (str): The name of the file that will be searched for
            in ``paths``
        paths (list): A list of paths that will be searched for ``filename``
    Returns:
        list: A list of file paths that were found
    """
    return [os.path.join(path, filename) for path in paths
            if os.path.isfile(os.path.join(path, filename))]

# Utils for permissions and user
###############################################################################

def get_uid():
    """Get the UID of the user that started uberdot.

    This gets the current users UID. If SUDO_UID is set (this means the process
    was started with sudo) SUDO_UID will be returned instead.

    Returns:
        (int): UID of the user that started uberdot
    """
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        return int(sudo_uid)
    return os.getuid()


def get_gid():
    """Get the GID of the user that started uberdot.

    This gets the current users GID. If SUDO_GID is set (this means the process
    was started with sudo) SUDO_GID will be returned instead.

    Returns:
        (int): GID of the user that started uberdot
    """
    sudo_gid = os.environ.get('SUDO_GID')
    if sudo_gid:
        return int(sudo_gid)
    return os.getgid()


def predict_owner(filename):
    """Gets the owner of the directory of a (non existing) file.

    If the the directory does not exist, this function will goes the directory
    tree up until it finds an existing directory and returns its owner instead.
    This is used to figure out which permission shall have if it is about to be
    created.

    Args:
        filename (str): (Non existing) absolute path to file
    Returns:
        A tuple containing the UID of the directory owner and the GID of the
        directory owner
    """
    dirname = os.path.dirname(filename)
    while not os.path.isdir(dirname):
        dirname = os.path.dirname(dirname)
    return ids_to_owner_string(get_owner(dirname))


def ids_to_owner_string(ids):
    return get_username(ids[0]) + ":" + get_groupname(ids[1])


def get_owner(filename):
    stat = os.lstat(filename)
    return stat.st_uid, stat.st_gid


def get_permission(filename):
    return int(oct(os.lstat(filename).st_mode)[-3:])


def inflate_owner(owner_string):
    user, group = owner_string.split(":")
    user = expandvars(user)
    group = expandvars(group)
    if not user:
        user = const.user
    if not group:
        group = get_groupname(get_gid())
    return user + ":" + group


def readlink(file):
    if os.path.islink(file):
        path = os.path.join(os.path.dirname(file), os.readlink(file))
        path = normpath(path)
        return path
    return file


def get_linkdescriptor_from_file(file):
    if not os.path.exists(file):
        raise FileNotFoundError
    if not os.path.islink(file):
        # This should be possible later on when hardlinks are supported
        raise NotImplementedError
    from uberdot.state import AutoExpandDict
    props = AutoExpandDict()
    target_file = readlink(file)
    props["from"] = file
    props["to"] = target_file
    uid, gid = get_owner(file)
    props["owner"] = get_username(uid) + ":" + get_groupname(gid)
    props["permission"] = get_permission(target_file)
    if os.path.exists(target_file):
        props["secure"] = get_owner(file) == get_owner(target_file)
    else:
        props["secure"] = None
    props["date"] = timestamp_to_string(os.path.getmtime(file))
    return props


def has_root_priveleges():
    """Checks if this programm has root priveleges.

    Returns:
        bool: True, if the current process has root priveleges
    """
    return os.geteuid() == 0


def get_username(uid):
    """Gets the username of a given uid.

    Returns:
        str: The username of the uid
    """
    return pwd.getpwuid(uid).pw_name


def get_groupname(gid):
    """Gets the groupname of a given gid.

    Returns:
        str: The groupname of the gid
    """
    return grp.getgrgid(gid).gr_name


def get_owner_ids(owner_string):
    user, group = owner_string.split(":")
    return pwd.getpwnam(user)[2], grp.getgrnam(group)[2]


def get_user_env_var(varname, fallback=None):
    """Lookup an environment variable.

    If executed as root, this function will login as the original user
    and look up the variable there. This means that this function will fail to
    look up environment variables that are for example set by the user in his
    .bashrc, because they aren't set at the time they will be looked up.
    Otherwise this function will do a standart look up of the users environment
    variables which means that all variables that were set at the time
    uberdot was started can be accessed.

    Args:
        varname (str): Name of the variable to look up
        fallback (str): A fallback value if ``varname`` does not exist
    Raises:
        :class:`~errors.PreconditionError`: The variable does not exist and no
            fallback value was set
    Returns:
        str: The value of the variable
    """
    if has_root_priveleges():
        # Looks like we have to load the environment vars by ourself
        user_environ = {}
        # Login into other user and read env
        proc = subprocess.run(
            ["sudo", "-Hiu", const.user, "env"],
            stdout=subprocess.PIPE
        )
        for line in proc.stdout.splitlines():
            key, val = line.decode().split("=", 1)
            user_environ[key] = val
        # User environ is loaded, so we can lookup
        try:
            return user_environ[varname]
        except KeyError:
            if fallback is not None:
                return fallback
            msg = "There is no environment varibable set for user '"
            msg += const.user + "' with the name: '"
            msg += varname + "'"
            raise PreconditionError(msg)
    # A normal user can access its own variables
    try:
        return os.environ[varname]
    except KeyError:
        if fallback is not None:
            return fallback
        raise PreconditionError("There is no environment varibable set " +
                                "with the name: '" + varname + "'")

def expandvars(path):
    """Behaves like the ``os.path.expandvars()`` but uses
    :func:`get_user_env_var()` to look up the substitution.

    Args:
        path (str): The path that will be expanded
    Returns:
        str: The expanded path
    """
    if '$' not in path:
        return path
    # Regex match for eg both $HOME and ${HOME}
    _varprog = re.compile(r'\$(\w+|\{[^}]*\})', re.ASCII)
    search = _varprog.search
    start = '{'
    end = '}'
    i = 0
    # Replace all matches
    while True:
        match = search(path, i)
        if not match:
            break
        i, j = match.span(0)
        name = match.group(1)
        if name.startswith(start) and name.endswith(end):
            name = name[1:-1]
        tail = path[j:]
        path = path[:i] + get_user_env_var(name)
        i = len(path)
        path += tail
    return path


def expanduser(path):
    """Behaves like the ``os.path.expanduser()`` but uses
    :func:`get_user_env_var()` to look up the substitution.

    Args:
        path (str): The path that will be expanded
    Returns:
        str: The expanded path
    """
    if path and path[0] == "~":
        path = get_user_env_var("HOME") + path[1:]
    return path


def expandpath(path):
    """Expands ~ and environment variables.

    Args:
        path (str): The path that will be expanded
    Returns:
        str: The expanded path
    """
    if path is not None:
        path = expandvars(path)
        return expanduser(path)
    return None


def normpath(path):
    """Normalizes path, expands ~ and environment vars,
    and converts it in an absolute path.

    Args:
        path (str): The path that will be normalized
    Returns:
        str: The normalized path
    """
    if path is not None:
        path = expandpath(path)
        return os.path.abspath(path)
    return None


# Dynamic imports
###############################################################################

def import_profile(class_name):
    """Imports a profile class only by it's name.

    Searches :const:`~constants.PROFILE_FILES` for python modules and imports
    them temporarily. If the module has a class that is the same as
    ``class_name`` it returns it.

    Args:
        class_name (str): The name of the class that will be imported
        file (str): If set, ``class_name`` will be imported from this file
            directly
    Raises:
        :class:`~errors.GenerationError`: One of the modules in
            :const:`~constants.PROFILE_FILES` contained errors or the imported
            class doesn't inherit from :class:`~profile.Profile`
        :class:`~errors.PreconditionError`: No class with the provided name
            exists
    Returns:
        class: The class that was imported
    """

    # Go through all python files in the profile directory
    for file in walk_profiles():
        imported = import_profile_class(class_name, file)
        if imported is not None:
            return imported
    raise PreconditionError("The profile '" + class_name +
                            "' could not be found in any module. Aborting.")


def import_profile_class(class_name, file):
    # Import profile (can't be done globally because profile needs to
    # import this module first)
    from uberdot.profile import Profile
    try:
        module = import_module(file, supress=False)
    except Exception as err:
        raise GenerationError(class_name, "The module '" + file +
                              "' contains an error and therefor " +
                              "can't be imported. The error was:" +
                              "\n   " + str(err))
    # Return the class if it is in this module
    if class_name in module.__dict__:
        if issubclass(module.__dict__[class_name], Profile):
            return module.__dict__[class_name]
        msg = "The class '" + class_name + "' does not inherit from"
        msg += " Profile and therefore can't be imported."
        raise GenerationError(class_name, msg)


def import_module(file, supress=True):
    # Import profile (can't be done globally because profile needs to
    # import this module first)
    from uberdot.profile import Profile
    try:
        spec = importlib.util.spec_from_file_location("__name__", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as err:
        if not supress:
            raise err

def get_available_profiles():
    # Import profile (can't be done globally because profile needs to
    # import this module first)
    from uberdot.profile import Profile
    result = []
    # Go through all python files in the profile directory
    for file in walk_profiles():
        module = import_module(file)
        if module is None:
            continue
        for name, field in module.__dict__.items():
            if isinstance(field, type):
                if issubclass(field, Profile):
                    if name != "Profile" and field.__module__ == "__name__":
                        result.append((file, name))
    return result



# Tools for iterators
###############################################################################
def nth(iterable, n, default=None):
    "Returns the nth item or a default value"
    return next(islice(iterable, n, None), default)


# Userinput and output
###############################################################################

def log(message, end="\n"):
    """Alias for logger.info() but creates a newline.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message: The message that will be logged
    """
    logger = logging.getLogger("root")
    logger.info(message + end)


def log_operation(profile_name, message, debug=False):
    """Logs/Prints out a message for a profile.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        profile_name (str): The name of the profile that triggered the operation.
        message (str): The message that will be logged
    """
    _log = log_debug if debug else log
    _log(const.settings.col_emph + "[" + profile_name + "]: " +
         const.col_noemph + message)


def log_warning(message, end="\n"):
    """Alias for logger.warning() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.warning(const.settings.col_warning + message + const.col_endc + end)


def log_success(message, end="\n"):
    """Alias for logger.info() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.info(const.settings.col_ok + message + const.col_endc + end)


def log_debug(message, end="\n"):
    """Alias for logger.debug() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.debug(const.settings.col_debug + message + const.col_endc + end)


def log_error(message, end="\n"):
    """Alias for logger.error() but creates a newline.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.error(message + end)


def user_choice(*options, abort=False):
    options = dict(options)
    if abort:
        options["A"] = "Abort"
    for key, text in options.items():
        idx = text.index(key)
        options[key] = text[:idx] + "[" + key + "]" + text[idx+1:]

    while True:
        selection = user_input(" / ".join(options.values()))
        selection = selection.lower().strip()
        if selection not in map(str.lower, options.keys()):
            print("Invalid option.")
        elif abort and selection == "a":
            raise UserAbortion()
        else:
            return selection


def user_confirmation(challenge):
    inp = user_input("Type \"" + challenge + "\" to confirm or anything else to abort")
    if challenge != inp:
        raise UserAbortion()


def user_selection(description, preselect=None):
    txt = description
    if preselect is not None:
        txt += " " + "[" + (" " if not preselect else preselect) + "]"
    inp = user_input(txt)
    if inp:
        return inp
    elif preselect:
        return preselect
    else:
        user_selection(description, preselect)

def user_input(txt):
    inp = input(txt + ": ")
    if const.test:
        print(inp)
        sys.stdout.flush()
    return inp



# Misc
###############################################################################

def get_profile_source(profile_name, file=None):
    if file is None:
        for path, name in get_available_profiles():
            if name == profile_name:
                file = path
                break
        else:
            msg = "Could not find module for '" + profile_name + "'"
            raise PreconditionError(msg)

    # This is a modified version inspect.getsource() because
    # the way we import profiles on-demand fucks with inspect,
    # so that it can't find the module of the profiles
    pat = re.compile(r'^(\s*)class\s*' + profile_name + r'\b')
    # make some effort to find the best matching class definition:
    # use the one with the least indentation, which is the one
    # that's most probably not inside a function definition.
    candidates = []
    lines = open(file).readlines()
    start = None
    for i in range(len(lines)):
        match = pat.match(lines[i])
        if match:
            # if it's at toplevel, it's already the best one
            if lines[i][0] == 'c':
                start = i
            # else add whitespace to candidate list
            candidates.append((match.group(1), i))
    if start is None:
        # this will sort by whitespace, and by line number,
        # less whitespace first
        candidates.sort()
        start = candidates[0][1]
    return inspect.getblock(lines[start:])


def links_similar(sym1, sym2):
    return sym1["from"] == sym2["from"] or sym1["to"] == sym2["to"]


def links_equal(link1, link2):
    return link1["from"] == link2["from"] and \
           link1["to"] == link2["to"] and \
           link1["owner"] == link2["owner"] and \
           link1["permission"] == link2["permission"] and \
           link1["secure"] == link2["secure"]


def link_exists(link):
    try:
        link2 = get_linkdescriptor_from_file(link["from"])
    except FileNotFoundError:
        return False
    return links_equal(link, link2)


def similar_link_exists(link):
    try:
        link2 = get_linkdescriptor_from_file(link["from"])
    except FileNotFoundError:
        return False
    return links_similar(link, link2)


def makedirs(dir_):
    if not os.path.exists(os.path.dirname(dir_)):
        makedirs(os.path.dirname(dir_))
    if not os.path.exists(dir_):
        log_debug("Creating directory '" + dir_ + "'")
        os.mkdir(dir_)


def get_timestamp_now():
    """Returns a timestamp string for the current moment

    Returns:
        str: The timestamp
    """
    return str(math.floor(time.time()))


def get_date_time_now():
    """Returns a datetime string for the current moment in the format
    YYYY-MM-DD hh:mm:ss

    Returns:
        str: The datetime string
    """
    return timestamp_to_string(get_timestamp_now())


def timestamp_to_string(timestamp):
    return datetime.datetime.utcfromtimestamp(
        math.floor(int(timestamp))
    ).strftime("%Y-%m-%d %H:%M:%S")


def is_dynamic_file(target):
    """Returns if a given path is a dynamic file.

    Args:
        target (str): The path to the file
    Returns:
        bool: True, if given path is a dynamicfile
    """
    dyn_dir = os.path.dirname(os.path.dirname(normpath(target)))
    if os.path.basename(dyn_dir) != "dynamicfiles":
        return False
    session_dir = os.path.dirname(dyn_dir) + "/"
    if session_dir == const.session_dir:
        return True
    for _, dir_foreign in const.session_dirs_foreign:
        if session_dir == dir_foreign:
            return True
    return False


def md5(string):
    """Calculate the md5 hash for a given string or bytearray.

    Args:
        string: A string or bytearray that the md5 hash will be
            calculated for. Strings will be encoded before hashing.
    Returns:
        The hexadecimal representation of the md5 hash
    """
    if isinstance(string, str):
        string = string.encode()
    return hashlib.md5(string).hexdigest()


# Custom errors
###############################################################################
class CustomError(Exception):
    """A base class for all custom exceptions.

    Attributes:
        _message (str): The original unformated error message
        message (str): The formatted colored error message
    """
    def __init__(self, message):
        """Constructor

        Args:
            message (str): The error message
        """
        self._message = message
        super().__init__()

    @property
    @abstractmethod
    def EXITCODE(self):
        """The exitcode that will be returned when this exception is raised.
        This needs to be implemented by subclasses.
        """
        raise NotImplementedError

    @property
    def message(self):
        msg = const.settings.col_fail + const.settings.col_emph + "ERROR: " + const.col_endc
        msg += const.settings.col_fail + self._message + const.col_endc
        return msg


class FatalError(CustomError):
    """A custom exception for all errors that violate expected invariants."""

    EXITCODE = 69
    """The exitcode for a FatalError"""

    def __init__(self, message="Unkown Error"):
        """Constructor.

        Adds a disclaimer that this error is indeed really bad.

        Args:
            message (str): The error message
        """
        msg = message
        msg += "\n" + const.settings.col_warning + "This error should NEVER EVER "
        msg += "occur!! The developer fucked this up really hard! Please "
        msg += "create an issue on github and wait for a patch before "
        msg += "using this tool again!" + const.col_endc
        super().__init__(msg)


class UserError(CustomError):
    """A custom exception for all errors that occur because the user didn't
    used the program correctly.

    :Example: --parent was specified without using -i.
    """

    EXITCODE = 101
    """The exitcode for a UserError"""

    def __init__(self, message):
        """Constructor.

        Adds a hint how to show help.

        Args:
            message (str): The error message
        """
        message += "\nUse 'udot --help' or 'udot {mode} --help' for a short overview of the CLI."
        message += "\nUse 'udot help' to display the man page."
        super().__init__(message)


class IntegrityError(CustomError):
    """A custom exception for all errors that occur because there are logical/
    sematic errors in a profile written by the user.

    :Example: A link is defined multiple times with different targets.
    """

    EXITCODE = 102
    """The exitcode for a IntegrityError"""


class PreconditionError(CustomError):
    """A custom exception for all errors that occur due to preconditions
    or expectations that are not fullfilled.

    :Example: A link that is defined in the state file doesn't exist
        on the system.
    """

    EXITCODE = 103
    """The exitcode for a PreconditionError"""


class GenerationError(CustomError):
    """A custom exception for all errors that occur during generation.

    :Example: The profile has syntax errors or a dotfile can't be found.
    """

    EXITCODE = 104
    """The exitcode for a GenerationError"""

    def __init__(self, profile_name, message):
        """Constructor.

        Adds the name of the profile that triggered the error to the message.

        Args:
            profile_name (str): Name of the profile that triggered the error
            message (str): The error message
        """
        super().__init__(const.settings.col_emph + "[" + profile_name + "]: " +
                         const.col_endc + message)


class UnkownError(CustomError):
    """A custom exception for all errors that are not expected/unkown.

    Used in pokemon handlers of critical sections to convert all unexpected
    errors into CustomException.
    """

    EXITCODE = 105
    """The exitcode for a UnkownError"""

    def __init__(self, original_error, message):
        """Constructor.

        Adds the type and the message of the original error to the error
        message.

        Args:
            original_error (Exception): The original exception that was catched
            message (str): An additional message for context
        """
        message += "\nThe unkown error was:\n  "
        message += type(original_error).__name__
        if str(original_error):
            message += ": " + str(original_error)
        super().__init__(message)


class UserAbortion(CustomError):
    """Used to abort uberdot at any given point safely by the user."""

    EXITCODE = 106
    """The exitcode for a UserAbortion"""

    def __init__(self):
        """Constructor.

        Sets the error message to "Aborted by user".
        """
        super().__init__("Aborted by user")


class SystemAbortion(CustomError):
    """Used to abort uberdot by the system."""

    EXITCODE = 107
    """The exitcode for a SystemAbortion"""


# Constants and loaded settings
###############################################################################
class Constant:
    FINAL=0
    MUTABLE=1
    CONFIGABLE=2
    def __init__(self, value, section, type, func, mutable):
        self.__dict__["value"] = value
        self.section = section
        self.type = type
        self.func = func
        self.mutable = mutable

    def __setattr__(self, name, value):
        if name == "value":
            if not self.mutable:
                raise ValueError("Constant is immutable")
            if self.func is not None:
                value = self.func(value)
        super().__setattr__(name, value)

    def __repr__(self):
        rep = "{"
        rep += "value: " + repr(self.value) + ", "
        rep += "section: " + str(self.section) + ", "
        rep += "type: " + self.type + ", "
        rep += "func: " + str(self.func) + ", "
        rep += "mutable: " + str(self.mutable)
        rep += "}"
        return rep


class Container:
    def __init__(self, root=None):
        if root is None:
            root = self
        self.root = root
        self.subcommand_container = self
        self.subcommand = None

    def __setattr__(self, name, value):
        if hasattr(self, name):
            attr = super().__getattribute__(name)
            if isinstance(attr, Constant):
                attr.value = value
                if name == "mode":
                    self.subcommand_container.subcommand = self.subcommand_container.__getattribute__(value)
            else:
                super().__setattr__(name, value)
        elif isinstance(value, Container) or isinstance(value, Constant) or value is None:
            super().__setattr__(name, value)
        else:
            raise AttributeError("Container has no attribute " + name)

    def __getattribute__(self, name):
        attribute = super().__getattribute__(name)
        if isinstance(attribute, Constant):
            return attribute.value
        return attribute

    def get_constants(self, mutable=Constant.CONFIGABLE):
        result = []
        for name, attr in self.__dict__.items():
            if isinstance(attr, Constant):
                if attr.mutable >= mutable and not name.isupper():
                    result.append((name, attr))
            elif isinstance(attr, Container) and attr.root != attr and name != "subcommand_container" and name != "subcommand":
                result.extend(attr.get_constants(mutable))
        return result

    def set(self, name, value):
        setattr(self, name, value)

    def __repr__(self):
        rep = "{"
        fields = []
        for name, attr in self.__dict__.items():
            if isinstance(attr, Constant):
                fields.append((name, attr))
            elif isinstance(attr, Container) and name != "root":
                rep += name + ": " + repr(attr) + ", "
        rep += ", ".join([
            name + ": " + repr(attr) for name, attr in fields
        ])
        rep += "}"
        return rep

    def get(self, name):
        return super().__getattribute__(name)

    def items(self):
        return [
            (name, props.value) for name, props in self.__dict__.items()
            if isinstance(props, Constant)
        ]

    def load_args(self, args, container=None):
        if container is None:
            container = self
        if hasattr(args, "mode") and args.mode is not None:
            container.mode = args.mode
        # Write arguments
        for arg, value in vars(args).items():
            if value is None or arg in ["config", "mode", "session"]:
                continue
            if isinstance(value, Namespace):
                self.get(arg).load_args(value)
                continue
            # TODO this is messed up and fucks with nesting
            # Parse tags and set values for --options
            if arg == "opt_dict":
                if "tags" in value:
                    value["tags"] = next(csv.reader([value["tags"]]))
                for key, val in value.items():
                    self.root.defaults.set(key, val)
                continue
            if arg == "directory":
                value = os.path.join(self.owd, value)
                self.root.defaults.set(arg, value)
                continue
            if arg == "include":
                self.root.args.set(arg, value)
                continue
            # Little fixes for arguments where the names don't match up
            # with the configuration file argument
            if arg == "log":
                value = os.path.join(self.owd, value)
                self.root.settings.set("logfile", value)
                continue
            # Relative paths need to be absolute
            if container.get(arg).type == "path":
                value = os.path.join(self.owd, value)
            elif container.get(arg).type == "int":
                value = int(value)
            # Set argument
            container.set(arg, value)


class OutsourcedContainer(Container):
    def __init__(self, parent, root=None):
        super().__init__(root)
        self.subcommand_container = parent


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Const(Container, metaclass=Singleton):
    section_mapping = {
        None: None,
        "args": "Arguments",
        "update": "Arguments:Update",
        "remove": "Arguments:Remove",
        "timewarp": "Arguments:Timewarp",
        "show": "Arguments:Show",
        "find": "Arguments:Find",
        "history": "Arguments:History",
        "help": "Arguments:help",
        "version": "Arguments:Version",
        "settings": "Settings",
        "defaults": "ProfileDefaults",
    }
    def __init__(self, **kwargs):
        super().__init__()
        # arguments for dot
        self.args = OutsourcedContainer(self, self)
        # arguments, depending on mode
        self.update = Container(self)
        self.remove = Container(self)
        self.find = Container(self)
        self.help = Container(self)  # Unused atm
        self.history = Container(self)  # Unused atm
        self.timewarp = Container(self)
        self.show = Container(self)
        self.version = Container(self)  # Unused atm
        # general settings, only settable via config
        self.settings = Container(self)
        # defaults for profiles
        self.defaults = Container(self)

        # create internal constants
        self.add("cfg_files", [], type="list", mutable=Constant.MUTABLE)
        self.add("cfg_search_paths", kwargs["cfg_search_paths"], type="list")
        self.add("col_endc", '\x1b[0m', mutable=Constant.MUTABLE)
        self.add("col_noemph", '\x1b[22m', mutable=Constant.MUTABLE)
        self.add("data_dir", kwargs["data_dir"], type="path")
        self.add("data_dirs_foreign", kwargs["data_dirs_foreign"], type="list")
        self.add("owd", os.getcwd(), type="path")
        self.add("session_dir", kwargs["session_dir"], type="path", mutable=Constant.MUTABLE)
        self.add("session_dirs_foreign", kwargs["session_dirs_foreign"], type="list", mutable=True)
        self.add("test", kwargs["test"], type="int")
        self.add("user", kwargs["user"])
        self.add("users", kwargs["users"], type="list")
        self.add("VERSION", kwargs["VERSION"])
        self.add("STATE_NAME", kwargs["STATE_NAME"])
        self.add("DATA_DIR_ROOT", kwargs["DATA_DIR_ROOT"])
        self.add("DATA_DIR_TEMP", kwargs["DATA_DIR_TEMP"])
        self.add("SESSION_SUBDIR", kwargs["SESSION_SUBDIR"])

        # create constants for arguments of dot
        add = self.add_factory(False, "args", "bool")
        add("skiproot", "summary")
        add("debuginfo", mutable=Constant.MUTABLE)
        self.add("exclude", [], "args", "list")
        self.add("fix", "", "args")
        self.add("mode", None, "args", mutable=Constant.MUTABLE)
        self.add("include", [], "args", "list")
        self.add("loglevel", logging.INFO, "args", func=self.__convert_loglevel)
        self.add("session", "default", "args", func=str.lower, mutable=Constant.MUTABLE)

        # create constants for arguments of parser_run
        add = self.add_factory(False, ["update", "remove", "timewarp"], "bool")
        add(
            "changes", "dryrun", "force", "skipafter",
            "skipbefore", "superforce", "debug", "makedirs"
        )
        add("skipevents", section=["update", "remove"])
        add("skipevents", value=True, section="timewarp")

        # create constants for arguments of update mode
        self.add("directory", "", "update", "path")
        self.add("dui", False, "update")
        self.add("parent", None, "update", "str")

        # create constants for arguments of show mode
        add = self.add_factory(False, "show", "bool")
        add("allusers", "links", "profiles", "meta")
        add("state", value=None, type="str", func=self.__find_state)
        add("users", value=[], type="list")

        # create constants for arguments of find mode
        add = self.add_factory(False, "find", "bool")
        add(
            "all", "content", "dotfiles", "filename", "ignorecase",
            "locations", "name", "profiles", "regex", "tags"
        )
        self.add("searchstr", section="find")

        # create constants for arguments of timewarp mode
        add = self.add_factory(
            False, "timewarp", "bool", mutable=Constant.MUTABLE
        )
        add("first", "last")
        add = self.add_factory(section="timewarp", mutable=Constant.MUTABLE)
        add("earlier", "later", func=self.__convert_interval)
        # add("date")
        add("state", func=self.__find_state)

        # create constants for settings
        add = self.add_factory(True, "settings", type="bool")
        add("askroot", "color", "smart_cd")
        self.add("backup_extension", "bak", "settings"),
        self.add("col_emph", '\x1b[1m', "settings", "str", self.__decode_ansi)
        self.add("col_fail", '\x1b[91m', "settings", "str", self.__decode_ansi)
        self.add("col_ok", '\x1b[92m', "settings", "str", self.__decode_ansi)
        self.add("col_warning", '\x1b[93m', "settings", "str", self.__decode_ansi)
        self.add("col_debug", '\x1b[90m', "settings", "str", self.__decode_ansi)
        self.add("decrypt_pwd", None, "settings")
        self.add("logfile", None, "settings", "path")
        self.add("logfileformat", "[%(asctime)s] [%(session)s] [%(levelname)s] - %(message)s", "settings")
        self.add("logfilesize", 0, "settings", "int")
        self.add("hash_separator", "#", "settings")
        self.add("profile_files", "", "settings", "path")
        self.add("shell", "/bin/bash", "settings", "path")
        self.add("shell_args", "-e -O expand_aliases", "settings")
        self.add("shell_timeout", 60, "settings", "int")
        self.add("tag_separator", "%", "settings")
        self.add("target_files", "", "settings", "path")

        # create constants for profile defaults
        add = self.add_factory(section="defaults")
        add(
            "extension", "name", "owner", "prefix",
            "replace", "replace_pattern", "suffix"
        )
        add("secure", value=True, type="bool")
        add("optional", value=False, type="bool")
        add("tags", value=[], type="list")
        add("directory", value="$HOME", type="path")
        add("permission", value=kwargs["permission"], type="int")

    def add(self, name, value="", section=None, type="str", func=None, mutable=None):
        if section is None:
            namespace = self
            if mutable is None:
                mutable = Constant.FINAL
            setattr(namespace, name, Constant(value, None, type, func, mutable))
        elif isinstance(section, list):
            for sec in section:
                self.add(name, value, sec, type, func, mutable)
        else:
            namespace = getattr(self, section)
            if mutable is None:
                mutable = Constant.CONFIGABLE
            setattr(namespace, name, Constant(value, self.section_mapping[section], type, func, mutable))

    def add_factory(self, value="", section=None, type="str", func=None, mutable=None):
        def add(*names, **params):
            params = {**{
                "value": value,
                "section": section,
                "type": type,
                "func": func,
                "mutable": mutable
            }, **params}
            for name in names:
                self.add(name, **params)
        return add

    ### Manipulation functions
    @staticmethod
    def __decode_ansi(string):
        return string.encode("utf-8").decode("unicode_escape")

    @staticmethod
    def __find_state(indicator):
        from uberdot.state import get_statefiles, build_statefile_path
        if re.fullmatch(r"\d{10}", indicator):
            # timestamp was provided
            return build_statefile_path(indicator)
        elif re.fullmatch(r"-?\d{1,9}", indicator):
            # number was provided
            number = int(indicator)
            if number == 0 or abs(number) >= len(get_statefiles()):
                raise UserError("Invalid state number.")
            elif number > 0:
                return nth(get_statefiles(), number-1)
            else:
                return nth(reversed(get_statefiles()), -number-1)
        else:
            return indicator

    @staticmethod
    def __convert_interval(string):
        if not re.fullmatch(r"(\d+[YMDhms])+", string):
            raise UserError("Invalid interval string")
        bits = re.findall(r"(\d+\w)", string)
        seconds = 0
        for bit in bits:
            val = int(bit[:-1])
            if bit[-1] == "Y":
                seconds += 60*60*24*30*12*val
            elif bit[-1] == "M":
                seconds += 60*60*24*30*val
            elif bit[-1] == "D":
                seconds += 60*60*24*val
            elif bit[-1] == "h":
                seconds += 60*60*val
            elif bit[-1] == "m":
                seconds += 60*val
            elif bit[-1] == "s":
                seconds += val
        return seconds

    @staticmethod
    def __convert_loglevel(level):
        level = level.upper()
        if level == "SILENT":
            return logging.CRITICAL
        elif level == "QUIET":
            return logging.WARNING
        elif level == "INFO":
            return logging.INFO
        elif level == "VERBOSE":
            return logging.DEBUG
        else:
            raise ValueError("No such loglevel")

    def load(self, args):
        # Find all configs
        cfgs = find_files("uberdot.ini", self.cfg_search_paths)
        if args.config:
           cfgs += [os.path.join(self.owd, args.config)]
        self.cfg_files = cfgs
        # Setup session
        if args.session:
            self.args.session = args.session
        self.session_dir = self.session_dir % self.args.session
        self.session_dirs_foreign = list(
            map(lambda x: (x[0], x[1] % self.args.session), self.session_dirs_foreign)
        )
        # Load configs
        config = configparser.ConfigParser(interpolation=None)
        try:
            for cfg in cfgs:
                if not os.path.exists(cfg):
                    raise PreconditionError("The config '" + cfg + "' does not exist.")
                config.read(cfg)
                # We need to normalize all paths here, relatively to
                # the config file which it defined
                path_values = [
                    "directory", "profile_files", "target_files", "logfile", "state"
                ]
                for section in config.sections():
                    for name, value in config.items(section):
                        if name in path_values and not re.fullmatch(r"\d{1,10}", value):
                            config[section][name] = os.path.normpath(
                                os.path.join(os.path.dirname(cfg), expandpath(value))
                            )
        except configparser.Error as err:
            msg = "Can't parse config at '" + cfg + "'. " + err.message
            raise PreconditionError(msg)
        # Write all values from config
        for name, props in self.get_constants():
            # Skip all internal values
            if props.section is None:
                continue
            # Set getter for config depending on value type
            getter = config.get
            if props.type == "int":
                getter = config.getint
            elif props.type == "bool":
                getter = config.getboolean
            # Get value from config. Prefer values from special session section
            section = "Session." + self.args.session + "." + props.section
            if config.has_section(section) and config.has_option(section, name):
                value = getter(section, name)
            elif config.has_section(props.section) and config.has_option(props.section, name):
                value = getter(props.section, name)
            else:
                # Value is not in config, skipping
                continue
            # Fix values depending on value type
            if props.type == "list":
                value = next(csv.reader([value]))
            props.value = value

        # Remove all colors if disabled
        if not self.settings.color:
            self.col_endc = ""
            for name, props in self.settings.get_constants():
                if name.startswith("col_"):
                    props.value = ""

        self.load_args(args, self.args)


def init_const():
    # Initialize basic constants
    VERSION = "1.18.0"
    STATE_NAME = "state.json"
    DATA_DIR_ROOT = "/root/.uberdot/"
    DATA_DIR_TEMP = "/home/%s/.uberdot/"
    SESSION_SUBDIR = "sessions/%s/"

    def gen_data_dir(user):
        if user == "root":
            path = DATA_DIR_ROOT
        else:
            path = DATA_DIR_TEMP % user
        return user, path

    user = get_username(get_uid())
    users = ["root"] + os.listdir("/home")
    users.remove(user)

    test = int(os.getenv("UBERDOT_TEST", 0))

    # Build/Prepare paths to stored data
    if not test:
        data_dir = gen_data_dir(user)[1]
        data_dirs_foreign = list(map(gen_data_dir, users))
        data_dirs_foreign = list(
            filter(lambda x: os.path.exists(x[1]), data_dirs_foreign)
        )
    else:
        # Using a dedicated data_dir that is tracked by git
        # so the tests can reset generated files and the logged state
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
            "test/regression/data"
        )
        # simulating a second user "test"
        data_dirs_foreign = [
            ("test", os.path.join(os.path.dirname(data_dir), "data_test"))
        ]
    # Directory of the current and all foreign sessions
    session_dir = os.path.join(data_dir, SESSION_SUBDIR)
    session_dirs_foreign = [
        (user, os.path.join(item, SESSION_SUBDIR)) for user, item in data_dirs_foreign
    ]
    # Searchpaths for configs
    cfg_search_paths = [
        "/etc/uberdot",
        os.path.join(
            get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
            "uberdot"
        ),
        os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
    ]

    # Find default permission (umask)
    open("/tmp/permission_test_file.tmp", "w").close()
    permission = get_permission("/tmp/permission_test_file.tmp")
    os.remove("/tmp/permission_test_file.tmp")

    # Create and initialize constant instance
    return Const(
        cfg_search_paths=cfg_search_paths,
        data_dir=data_dir,
        data_dirs_foreign=data_dirs_foreign,
        session_dir=session_dir,
        session_dirs_foreign=session_dirs_foreign,
        test=test,
        user=user,
        users=users,
        permission=permission,
        VERSION=VERSION,
        STATE_NAME=STATE_NAME,
        DATA_DIR_ROOT=DATA_DIR_ROOT,
        DATA_DIR_TEMP=DATA_DIR_TEMP,
        SESSION_SUBDIR=SESSION_SUBDIR
    )
const = init_const()
