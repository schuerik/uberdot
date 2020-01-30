"""Provides functionality that is needed in multiple modules.
E.g. retrieving a environment variable or fixing file permisions."""

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


import datetime
import hashlib
import grp
import importlib.util
import logging
import math
import os
import pwd
import re
import subprocess
import time
from uberdot import constants as const
from uberdot.errors import FatalError
from uberdot.errors import GenerationError
from uberdot.errors import PreconditionError


# Utils for finding targets
###############################################################################

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
            if name == tag + const.tag_separator + target:
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
    ignorelist_path = os.path.join(const.target_files, ".dotignore")
    ignorelist = []
    if os.path.exists(ignorelist_path):
        with open(ignorelist_path, "r") as file:
            ignorelist = file.readlines()
        ignorelist = [entry.strip() for entry in ignorelist]
    ignorelist.append(".dotignore")

    # walk through dotfile directory
    result = []
    for root, _, files in os.walk(const.target_files):
        for name in files:
            # check if file should be ignored
            on_ignorelist = False
            for entry in ignorelist:
                if re.search(entry, os.path.join(root, name)):
                    on_ignorelist = True
            # if not add it to result
            if not on_ignorelist:
                result.append((root, name))
    return result


def walk_profiles():
    result = []
    for root, _, files in os.walk(const.profile_files):
        for file in files:
            file = os.path.join(root, file)
            # Ignore everything that isn't a python module
            if file[-2:] == "py":
                result.append(file)
    return result


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


def get_dir_owner(filename):
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
    return os.stat(dirname).st_uid, os.stat(dirname).st_gid


def has_root_priveleges():
    """Checks if this programm has root priveleges.

    Returns:
        bool: True, if the current process has root priveleges
    """
    return os.geteuid() == 0


def get_current_username():
    """Gets the current users username.

    Gets the username of the user that started uberdot. If the
    program was started with sudo, it still returns the original
    username and not "root".

    Returns:
        str: The username of the current user
    """
    return get_username(get_uid())


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
            ["sudo", "-Hiu", get_current_username(), "env"],
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
            msg += get_current_username() + "' with the name: '"
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
        path = expandvars(path)
        path = expanduser(path)
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


# Misc
###############################################################################

logger = logging.getLogger("root")

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
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    """Alias for logger.info() but creates a newline.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message: The message that will be logged
    """
    logger.info(message + "\n")

def log_operation(profile_name, message):
    """Logs/Prints out a message for a profile.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        profile_name (str): The name of the profile that triggered the operation.
        message (str): The message that will be logged
    """
    logger.info(const.col_bold + "[" + profile_name + "]: " +
                const.col_nobold + message + "\n")


def log_warning(message):
    """Alias for logger.warning() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.warning(const.col_warning + message + const.col_endc + "\n")


def log_success(message):
    """Alias for logger.info() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.info(const.col_ok + message + const.col_endc + "\n")


def log_debug(message):
    """Alias for logger.debug() but creates a newline and colorizes output.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.debug(const.col_debug + message + const.col_endc + "\n")


def log_error(message):
    """Alias for logger.error() but creates a newline.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.error(message + "\n")


def is_dynamic_file(target):
    """Returns if a given path is a dynamic file.

    Args:
        target (str): The path to the file
    Returns:
        bool: True, if given path is a dynamicfile
    """
    return os.path.dirname(os.path.dirname(target)) == normpath("data")


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
