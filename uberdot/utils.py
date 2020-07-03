
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


from datetime import datetime
import csv
from argparse import Namespace
import shutil
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
import stat
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


def get_snapshots(state_dir):
    snapshots = []
    for file in listfiles(state_dir):
        if re.fullmatch(r".*/state_\d{10}\.json", file):
            snapshots.append(file)
    return sorted(snapshots)


def build_statefile_path(timestamp=None):
    path = os.path.join(const.internal.session_dir, const.internal.STATE_NAME)
    if timestamp is not None:  # Load a previous snapshot
        path, ext = os.path.splitext(path)
        path += "_" + timestamp + ext
    return path


def get_timestamp_from_path(path):
    return path.split("_")[1][:-5]


def get_tags_from_path(path):
    tag, base = (None, os.path.basename(path))
    if const.settings.tag_separator in base:
        *tags, base = base.split(const.settings.tag_separator)
        return tags
    return []


def strip_tags(filename):
    directory = os.path.dirname(filename)
    base = os.path.basename(filename)
    if const.settings.tag_separator in base:
        base = base.split(const.settings.tag_separator)[-1]
    return os.path.join(directory, base)


def strip_hashs(filename):
    directory = os.path.dirname(filename)
    base = os.path.basename(filename)
    if const.settings.hash_separator in base:
        splits = base.split(const.settings.hash_separator)
        # Strip only the last hash and rejoin the rest
        base = const.settings.hash_separator.join(splits[:-1])
    return os.path.join(directory, base)


def find_target_with_tags(target, tags):
    """Finds the correct target version in the repository to link to.

    This will search :const:`~constants.TARGET_FILES` for files that match the
    naming schema `<any string>%<target>` and returns the file whose
    `<any string>` occurs first in ``tags``.

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
        return None
    # Find the file that matches the earliest defined tag
    result_tag = None
    for tag in tags:
        for tmp_target in targets:
            if os.path.basename(tmp_target).startswith(tag):
                result_tag = tag
    # Check that only one file was found
    results = list(filter(lambda x: os.path.basename(x).startswith(result_tag), targets))
    if len(results) > 1:
        msg = "There are multiple targets that match: '" + target + "'"
        for tmp_target in results:
            msg += "\n  " + tmp_target
        raise ValueError(msg)
    return results[0]


def find_target_exact(target):
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

def listdirs(dirname):
    return filter(
        os.path.isdir,
        map(lambda x: os.path.join(dirname, x), os.listdir(dirname))
    )

def listfiles(dirname):
    return filter(
        os.path.isfile,
        map(lambda x: os.path.join(dirname, x), os.listdir(dirname))
    )

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
        # Return original path
        path = os.path.join(os.path.dirname(file), os.readlink(file))
        path = normpath(path)
        return True, path
    else:
        # file is hardlink, so return the inode number as reference for the original
        return False, os.stat(file).st_ino


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
    from uberdot.profile import ProfileSkeleton
    try:
        module = import_module(file, supress=False)
    except CustomError as err:
        raise err
    except Exception as err:
        raise GenerationError("The module '" + file +
                              "' contains an error and therefor " +
                              "can't be imported. The error was:" +
                              "\n   " + str(err), profile=class_name)
    # Return the class if it is in this module
    if class_name in module.__dict__:
        if issubclass(module.__dict__[class_name], ProfileSkeleton):
            return module.__dict__[class_name]
        msg = "The class '" + class_name + "' does not inherit from"
        msg += " Profile and therefore can't be imported."
        raise GenerationError(msg, profile=class_name)


def import_module(file, supress=True):
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
    from uberdot.profile import ProfileSkeleton
    result = []
    # Go through all python files in the profile directory
    for file in walk_profiles():
        module = import_module(file)
        if module is None:
            continue
        for name, field in module.__dict__.items():
            if isinstance(field, type):
                if issubclass(field, ProfileSkeleton):
                    # TODO: whats that
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

class StdoutFilter(logging.Filter):
    """Custom logging filter that filters all error messages from a stream.
    Used to filter stdout, because otherwise every error would be pushed to
    stdout AND stderr."""

    def filter(self, record):
        """Returns True for all records that have a logging level of
        WARNING or less."""
        return record.levelno <= logging.WARNING


class NoColorFileHandler(logging.FileHandler):
    def __init__(self, filename):
        super().__init__(filename)

    def emit(self, record):
        msg = record.msg
        # Remove all color codes
        msg = msg.replace(const.internal.col_endc, "")
        msg = msg.replace(const.internal.col_noemph, "")
        for name, attr in const.settings.get_constants():
            if name.startswith("col_"):
                msg = msg.replace(attr.value, "")
        record.msg = msg
        super().emit(record)


class CustomRecordLogger(logging.Logger):
    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        # Add custom attributes to LogRecords, so that they can be
        # used in format strings
        if extra is None:
            extra = {}
        extra["session"] = const.args.session
        extra["test"] = const.internal.test
        extra["user"] = const.internal.user
        extra["version"] = const.internal.VERSION
        return super().makeRecord(
            name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )


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
         const.internal.col_noemph + message)


def log_warning(message, end="\n"):
    """Alias for logger.warning() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.warning(const.settings.col_warning + message + const.internal.col_endc + end)


def log_success(message, end="\n"):
    """Alias for logger.info() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.info(const.settings.col_ok + message + const.internal.col_endc + end)


def log_debug(message, end="\n"):
    """Alias for logger.debug() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger = logging.getLogger("root")
    logger.debug(const.settings.col_debug + message + const.internal.col_endc + end)


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

def create_backup(filename):
    backupfile = filename + "." + const.settings.backup_extension
    try:
        shutil.copyfile(filename, backupfile)
        os.chmod(backupfile, 0o444)
    except Exception as err:
        msg = "An unknown error occurred when trying to create a backup of '"
        msg += filename + "'."
        raise UnkownError(err, msg)
    return backupfile


def create_tmp_backup(filename):
    backupfile = filename + "." + const.settings.backup_extension
    try:
        shutil.copyfile(filename, backupfile)
    except Exception as err:
        msg = "An unknown error occurred when trying to create a temporary "
        msg += "backup of '" + filename + "'."
        raise UnkownError(err, msg)
    return backupfile


def remove_tmp_backup(filename):
    backupfile = filename + "." + const.settings.backup_extension
    try:
        os.remove(backupfile)
    except Exception as err:
        msg = "An unknown error occurred when trying to remove a temporary "
        msg += "backup of '" + filename + "'."
        raise UnkownError(err, msg)
    return backupfile


def get_profile_source(profile_name, file=None):
    if file is None:
        for path, name in get_available_profiles():
            if name == profile_name:
                file = path
                break
        else:
            msg = "Could not find module for '" + profile_name + "'"
            raise PreconditionError(msg)

    # This is a modified version of inspect.getsource() because
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
    return datetime.utcfromtimestamp(
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
        msg = const.settings.col_fail + const.settings.col_emph + "ERROR: " + const.internal.col_endc
        msg += const.settings.col_fail + self._message + const.internal.col_endc
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
        msg += "using this tool again!" + const.internal.col_endc
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


# TODO unify all generation error messages
# a lot of times the orginal exception get shadowed and does not show line number
class GenerationError(CustomError):
    """A custom exception for all errors that occur during generation.

    :Example: The profile has syntax errors or a dotfile can't be found.
    """

    EXITCODE = 104
    """The exitcode for a GenerationError"""

    def __init__(self, message, profile=None):
        """Constructor.

        Adds the name of the profile that triggered the error to the message.

        Args:
            profile_name (str): Name of the profile that triggered the error
            message (str): The error message
        """
        if hasattr(sys, "_getframe"):
            # We can figure out the line number where the error occured
            frameinfo = None
            c = 1
            while frameinfo is None:
                try:
                    frame = sys._getframe(c)
                except ValueError:
                    break
                if frame.f_code.co_filename.startswith(const.settings.profile_files):
                    frameinfo = frame.f_code.co_filename, frame.f_lineno
                c += 1
        # Prepend the origin of the error to the message
        msg = ""
        # If we could figure out the correct frame that triggered the exception
        # we use the file and line number from the frame as origin
        if frameinfo is not None:
            msg += "in '" + frameinfo[0] + "'"
            if profile is not None:
                msg += " in class '" + profile + "'"
            msg += "line " + str(frameinfo[1]) + ": "
        # Otherwise we will only use the name of the profile
        elif profile is not None:
            msg += const.settings.col_emph + "[" + profile + "]: " + const.internal.col_endc
        msg += message
        super().__init__(msg)


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


class UnsupportedError(CustomError):
    """Used whenever a feature is not supported."""

    EXITCODE = 108
    """The exitcode for a UnsupportedError."""


# TODO: better name
class UberdotError(CustomError):
    """Used for all expected errors that are directly thrown from own components.

    E.g.: A constant that was set to be only changed once, was tried to be changed
    a second time.
    """

    EXITCODE = 109
    """The exitcode for a UberdotError."""


# Constants and loaded settings
###############################################################################
class Constant:
    # Constant can't be changed after initialization
    FINAL = 0
    # Constant can be changed after initialization, but only once (to be read from a config)
    CONFIGABLE = 1
    # Constant can be changed whithout restrictions (acts like a global variable)
    VARIABLE = 2

    def __init__(self, value, section, type, func, mutable):
        self.section = section
        self.type = type
        self.func = func
        self.__mutable = mutable
        self.__modification_counter = 0
        self._value = self.interpolate_value(value)

    @property
    def mutable(self):
        return self.__mutable

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if not self.__mutable:
            raise ValueError("Constant is immutable.")
        if self.__mutable == self.CONFIGABLE and self.__modification_counter > 0:
            raise ValueError("Constant was already modified.")
        self._value = self.interpolate_value(value)
        self.__modification_counter += 1

    def interpolate_value(self, value):
        # Apply interpolation function on raw input
        if self.func is not None:
            value = self.func(value)
        # Modify/Parse value depending on its type
        if self.type == "path":
            value = normpath(value)
        elif self.type == "int":
            value = int(value)
        elif self.type == "list":
            if type(value) == "str":
                value = next(csv.reader([value]))
        return value

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
    def __init__(self, parent=None):
        self.parent = parent

    def __setattr__(self, name, value):
        if hasattr(self, name):
            attr = super().__getattribute__(name)
            if isinstance(attr, Constant):
                attr.value = value
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

    def get_constants(self, mutable=Constant.VARIABLE):
        result = []
        for name, attr in self.__dict__.items():
            if isinstance(attr, Constant):
                if attr.mutable >= mutable and not name.isupper():
                    result.append((name, attr))
            elif isinstance(attr, Container) and attr.parent != self:
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
        for name, props in self.__dict__.items():
            if isinstance(props, Constant):
                yield (name, props.value)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# TODO: test new constant loading, arg loading, mutable feature and lazy loading
class Const(metaclass=Singleton):
    con_to_sec = {
        "internal": None,
        "args": "Arguments",
        "update": "Arguments:Update",
        "remove": "Arguments:Remove",
        "timewarp": "Arguments:Timewarp",
        "show": "Arguments:Show",
        "find": "Arguments:Find",
        "history": "Arguments:History",
        "help": "Arguments:Help",
        "version": "Arguments:Version",
        "settings": "Settings",
        "defaults": "ProfileDefaults",
    }

    def __init__(self, **kwargs):
        # Init own properies
        self.__load_initialized = False
        self.__initialized = False
        self.sec_to_con = {v: k for k, v in self.con_to_sec.items()}
        # Init constant containers
        # internal constants of uberdot
        self.internal = Container()
        # global arguments
        self.args = Container()
        # general settings, only settable via config
        self.settings = Container()
        # defaults for profiles
        self.defaults = Container()
        # list of above containers
        self.root_container = [
            self.defaults, self.settings, self.args, self.internal
        ]
        # arguments, depending on mode
        self.update = Container(self.args)
        self.args.update = self.update
        self.remove = Container(self.args)
        self.args.remove = self.remove
        self.find = Container(self.args)
        self.args.find = self.find
        self.help = Container(self.args)  # Unused atm
        self.args.help = self.help
        self.history = Container(self.args)  # Unused atm
        self.args.history = self.history
        self.timewarp = Container(self.args)
        self.args.timewarp = self.timewarp
        self.show = Container(self.args)
        self.args.show = self.show
        self.version = Container(self.args)  # Unused atm
        self.args.version = self.version

        # create internal constants
        add = self.add_factory("internal", mutable=Constant.FINAL)
        add("cfg_search_paths", value=kwargs["cfg_search_paths"], type="list")
        add("data_dir", value=kwargs["data_dir"], type="path")
        add("data_dirs_foreign", value=kwargs["data_dirs_foreign"], type="list")
        add("owd", value=os.getcwd(), type="path")
        add("test", value=kwargs["test"], type="int")
        add("user", value=kwargs["user"])
        add("users", value=kwargs["users"], type="list")
        add("VERSION", value=kwargs["VERSION"])
        add("MIN_VERSION", value=kwargs["MIN_VERSION"])
        add("STATE_NAME", value=kwargs["STATE_NAME"])
        add("DATA_DIR_ROOT", value=kwargs["DATA_DIR_ROOT"])
        add("DATA_DIR_TEMP", value=kwargs["DATA_DIR_TEMP"])
        add("SESSION_SUBDIR", value=kwargs["SESSION_SUBDIR"])
        add = self.add_factory("internal", mutable=Constant.CONFIGABLE)
        add("cfg_files", value=[], type="list")
        add("session_dir", value=kwargs["session_dir"], type="path", )
        add("session_dirs_foreign", value=kwargs["session_dirs_foreign"], type="list")
        add("col_endc", value='\x1b[0m')
        add("col_noemph", value='\x1b[22m')

        # create constants for global arguments of uberdot
        add = self.add_factory("args", value=False, type="bool")
        add("debuginfo", "skiproot", "summary")
        add("log", value=True)
        add = self.add_factory("args")
        add("exclude", value=[], type="list")
        add("fix")
        add("mode", value=None)
        add("loglevel", value="info", func=self.__convert_loglevel)
        add("session", value="default", func=str.lower)

        # create constants for arguments of parser_run
        # these are variable, so that the user can overwrite them from a profile
        add = self.add_factory(
            ["update", "remove", "timewarp"], value=False,
            type="bool", mutable=Constant.VARIABLE
        )
        add(
            "changes", "dryrun", "force", "skipafter",
            "skipbefore", "superforce", "debug", "makedirs"
        )
        add("include", value=[], type="list")
        add("skipevents", section=["update", "remove"])
        add("skipevents", value=True, section="timewarp")

        # create constants for extra arguments of update mode
        add = self.add_factory("update")
        add("directory", value="", type="path")
        add("dui", value=False, type="bool")
        add("parent", value=None)

        # create constants for extra arguments of timewarp mode
        add = self.add_factory("timewarp", value=False, type="bool")
        add("first", "last")
        add = self.add_factory("timewarp")
        add("earlier", "later", func=self.__convert_interval)
        add("date", func=self.__parse_date)
        add("state", func=self.__find_state, type="state")

        # create constants for arguments of show mode
        add = self.add_factory("show", value=False, type="bool")
        add("allusers", "links", "profiles", "meta")
        add("include", value=[], type="list")
        add("state", value=None, type="state", func=self.__find_state)
        add("users", value=[], type="list")

        # create constants for arguments of find mode
        add = self.add_factory("find", value=False, type="bool")
        add(
            "all", "content", "dotfiles", "filename", "ignorecase",
            "locations", "name", "profiles", "regex", "tags"
        )
        self.add("searchstr", "find")

        # create constants for settings
        add = self.add_factory("settings", value=True, type="bool")
        add("askroot", "color", "smart_cd")
        add = self.add_factory(
            "settings", func=self.__decode_ansi, mutable=Constant.VARIABLE
        )
        add("col_emph", value='\x1b[1m')
        add("col_fail", value='\x1b[91m')
        add("col_ok", value='\x1b[92m')
        add("col_warning", value='\x1b[93m')
        add("col_debug", value='\x1b[90m')
        add = self.add_factory("settings")
        add("backup_extension", value="bak"),
        add("decrypt_pwd", value=None)
        add(
            "logfileformat",
            value="[%(asctime)s] [%(session)s] [%(levelname)s] - %(message)s"
        )
        add("logfilesize", value=0, type="int")
        add("logfile", value="$HOME/uberdot.log", type="path")
        add("hash_separator", value="#")
        add("profile_files", type="path")
        add("shell", value="/bin/bash", type="path")
        add("shell_args", value="-e -O expand_aliases")
        add("shell_timeout", value=60, type="int")
        add("tag_separator", value="%")
        add("target_files", type="path")

        # create constants for profile defaults
        add = self.add_factory("defaults")
        add(
            "extension", "name", "owner", "prefix",
            "replace", "replace_pattern", "suffix"
        )
        add("secure", value=True, type="bool")
        add("optional", value=False, type="bool")
        add("tags", value=[], type="list")
        add("directory", value="$HOME", type="path")
        add("permission", value=kwargs["permission"], type="int")

        # Done
        self.__initialized = True

    def export_dump(self, *extra_data, filename="udot.pickle"):
        pickle.dump([self, *extra_data], open(filename))

    def import_dump(self, filename="udot.pickle"):
        if os.path.exists(filename):
            data = pickle.load(open(filename))
            # TODO: I dont believe this works. Also i dont know if we can
            # overwrite readonly properties of this singleton containser.
            self = data[0]
            return data[1:]

    def add(
        self, name, section,
        value="", type="str", func=None, mutable=Constant.CONFIGABLE
    ):
        if isinstance(section, list):
            for sec in section:
                self.add(name, sec, value, type, func, mutable)
            return
        else:
            constant = Constant(
                value, self.con_to_sec[section], type, func, mutable
            )
            setattr(getattr(self, section), name, constant)
            if self.__load_initialized:
                self.__load_value(name, constant)

    def add_factory(
        self, section,
        value="", type="str", func=None, mutable=Constant.CONFIGABLE
    ):
        def add(*names, **params):
            params = {**{
                "section": section,
                "value": value,
                "type": type,
                "func": func,
                "mutable": mutable
            }, **params}
            for name in names:
                self.add(name, **params)
        return add

    def get(self, name):
        return self.__dict__[name]

    ### Manipulation functions
    @staticmethod
    def __decode_ansi(string):
        return string.encode("utf-8").decode("unicode_escape")

    @staticmethod
    def __find_state(indicator):
        if not indicator:
            return indicator
        if re.fullmatch(r"\d{10}", indicator):
            # timestamp was provided
            return build_statefile_path(indicator)
        elif re.fullmatch(r"-?\d{1,9}", indicator):
            # number was provided
            number = int(indicator)
            snapshots = get_snapshots(const.session_dir)
            if number == 0 or abs(number) > len(snapshots):
                raise UserError("Invalid state number.")
            elif number > 0:
                return snapshots[number-1]
            else:
                return nth(reversed(snapshots), -number-1)
        else:
            return indicator

    @staticmethod
    def __parse_date(string):
        if not string:
            return string
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}", string):
            return int(datetime.strptime(string, "%Y-%m-%d-%H:%M:%S").timestamp())
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}", string):
            return int(datetime.strptime(string, "%Y-%m-%d-%H:%M").timestamp())
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", string):
            return int(datetime.strptime(string, "%Y-%m-%d").timestamp())
        elif re.fullmatch(r"\d{4}-\d{2}", string):
            return int(datetime.strptime(string, "%Y-%m").timestamp())
        elif re.fullmatch(r"\d{4}", string):
            return int(datetime.strptime(string, "%Y").timestamp())
        else:
            raise UserError("Invalid datetime string")

    @staticmethod
    def __convert_interval(string):
        if not string:
            return string
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

    def get_constant(self, section, name):
        if section is None:
            return self.get(name)
        return self.get(self.sec_to_con[section]).get(name)

    def load(self, args):
        self.parsed_args = args
        # Find all configs
        cfgs = find_files("uberdot.ini", self.internal.cfg_search_paths)
        if args.config:
            cfgs += [os.path.join(self.internal.owd, args.config)]
        self.internal.cfg_files = cfgs
        # Setup session
        if args.session:
            self.args.session = args.session
        self.internal.session_dir = self.internal.session_dir % self.args.session
        self.internal.session_dirs_foreign = list(
            map(
                lambda x: (x[0], x[1] % self.args.session),
                self.internal.session_dirs_foreign
            )
        )
        # Prepare config load
        all_constants = []
        for container in self.root_container:
            all_constants += container.get_constants(mutable=Constant.CONFIGABLE)
        # Load configs
        self.config = configparser.ConfigParser(interpolation=None)
        try:
            for cfg in cfgs:
                if not os.path.exists(cfg):
                    raise PreconditionError("The config '" + cfg + "' does not exist.")
                self.config.read(cfg)
                # Check and normalize the read config
                for section in self.config.sections():
                    sec = section
                    if section.startswith("Session"):
                        sec = section.split(".")[-1]
                    for name, value in self.config.items(section):
                        # Get corresponding constant
                        constant = self.get_constant(sec, name)
                        # We need to normalize all paths here, relatively to
                        # the config file which it defined
                        if (constant.type == "state" and not re.fullmatch(r"\d{1,10}", value)) \
                                or constant.type == "path":
                            self.config[section][name] = os.path.normpath(
                                os.path.join(os.path.dirname(cfg), expandpath(value))
                            )
        except configparser.Error as err:
            msg = "Can't parse config at '" + cfg + "'. " + err.message
            raise PreconditionError(msg)

        self.__load_initialized = True

        # Write all values from config
        for name, constant in all_constants:
            if name == "session" and constant.section == self.con_to_sec["args"]:
                continue
            self.__load_value(name, constant)

        # Create shortcut to arguments of current mode
        self.mode_args = self.get(self.args.mode)

        # Remove all colors if disabled
        if not self.settings.color:
            self.internal.col_endc = ""
            for name, props in self.settings.get_constants():
                if name.startswith("col_"):
                    props.value = ""

    def __load_value(self, name, constant):
        if not self.__load_initialized:
            raise FatalError("Config loading feature not fully initialized yet.")
        if constant.section is None:
            # Constant can't be found in any config
            return
        # Set getter for config depending on value type
        getter = self.config.get
        if constant.type == "int":
            getter = self.config.getint
        elif constant.type == "bool":
            getter = self.config.getboolean
        # Try to load value from parsed_args
        loaded, value = self.__get_value_from_args(name, constant)
        if not loaded:
            # Try to load value from config. Prefer special session section.
            section = "Session." + self.args.session + "." + constant.section
            if self.config.has_section(section) and self.config.has_option(section, constant):
                value = getter(section, name)
                loaded = True
            elif self.config.has_section(constant.section) and self.config.has_option(constant.section, name):
                value = getter(constant.section, name)
                loaded = True
            else:
                # Value is not in config. We don't change the value, but set it
                # anyway so that the constant can't be overwritten anymore
                value = constant.value
        # Set constant, if possible
        try:
            constant.value = value
        except ValueError as err:
            raise UberdotError("Cannot set constant '" + name + "'. " + str(err))

    def __get_value_from_args(self, name, constant):
        found = False
        value = None
        pargs = vars(self.parsed_args)  # dict to search in
        con = self.sec_to_con[constant.section]  # name of container in constants

        # Filter constants that cant be set via commandline anyway
        if con in ["internal", "settings"]:
            return found, value

        # Select the correct section of parsed_args
        if con == "default" and "update" in pargs and "opt_dict" in pargs["update"] and pargs["update"]["opt_dict"] is not None:
            pargs = vars(pargs["update"]["opt_dict"])
        elif con in pargs:
            pargs = vars(pargs[con])

        # Search for the argument
        if name in pargs and pargs[name] is not None:
            value = pargs[name]
            found = True

            # Fix value depending on type
            if constant.type == "path":
                value = os.path.join(self.owd, value)
            # TODO
            # elif constant.type == "state":
            #     value = os.path.join(self.owd, value)
            elif constant.type == "int":
                value = int(value)
        return found, value


def init_const():
    # Initialize basic constants
    VERSION = "1.18.0"
    MIN_VERSION = "1.12.17_4"
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

    # Create and initialize Const instance
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
        MIN_VERSION=MIN_VERSION,
        STATE_NAME=STATE_NAME,
        DATA_DIR_ROOT=DATA_DIR_ROOT,
        DATA_DIR_TEMP=DATA_DIR_TEMP,
        SESSION_SUBDIR=SESSION_SUBDIR
    )
const = init_const()
