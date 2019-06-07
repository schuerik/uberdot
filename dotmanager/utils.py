"""Provides functionality that is needed in multiple modules.
Eg. Retrieving a environment variable or fixing file permisions"""

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
###############################################################################


import datetime
import importlib.util
import logging
import os
import pwd
import re
import subprocess
from dotmanager import constants
from dotmanager.errors import FatalError
from dotmanager.errors import GenerationError
from dotmanager.errors import PreconditionError


# Utils for finding targets
###############################################################################

def find_target(target, tags):
    """Finds the correct target version in the repository to link to.

    This will search ``constants.TARGET_FILES`` for files that match the naming
    schema `<any string>%<target>` and returns the file whose `<any string>`
    occurs first in ``tags``. If no file is found the return value of
    ``find_exact_target()`` is returned.

    Args:
        target (str): The filename that will be searched for
        tags (List): A list of tags that will be matched against the search
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
            if name == tag + "%" + target:
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

    This will search ``constants.TARGET_FILES`` for files that match
    ``target``.

    Args:
        target (str): The filename that will be searched for
    Raises:
        ValueError: Multiple targets where found
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
    """Walks through the ``constants.TARGET_FILES`` and returns all files
    found.

    This also takes the .dotignore-file into account.

    Returns:
        (List): Contains tuples with the directory and the filename of every
        found file
    """
    # load ignore list
    ignorelist_path = os.path.join(constants.TARGET_FILES, ".dotignore")
    ignorelist = []
    if os.path.exists(ignorelist_path):
        with open(ignorelist_path, "r") as file:
            ignorelist = file.readlines()
        ignorelist = [entry.strip() for entry in ignorelist]

    # walk through dotfile directory
    result = []
    for root, _, files in os.walk(constants.TARGET_FILES):
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


# Utils for permissions and user
###############################################################################

def get_uid():
    """Get the UID of the user that started dotmanager.

    This gets the current users UID. If SUDO_UID is set (this means the process
    was started with sudo) SUDO_UID will be returned instead.

    Returns:
        (int): UID of the user that started dotmanger
    """
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        return int(sudo_uid)
    return os.getuid()


def get_gid():
    """Get the GID of the user that started dotmanager.

    This gets the current users GID. If SUDO_GID is set (this means the process
    was started with sudo) SUDO_GID will be returned instead.

    Returns:
        (int): GID of the user that started dotmanger
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

    Gets the username of the user that started Dotmanager. If the
    program was started with sudo, it still returns the original
    username and not "root".

    Returns:
        str: The username of the current user
    """
    return pwd.getpwuid(get_uid()).pw_name


def get_user_env_var(varname, fallback=None):
    """Lookup an environment variable.

    If executed as root, this function will login as the original user
    and look up the variable there. This means that this function will fail to
    look up environment variables that are for example set by the user in his
    .bashrc, because they aren't set at the time they will be looked up.
    Otherwise this function will do a standart look up of the users environment
    variables which means that all variables that were set at the time
    Dotmanager was started can be accessed.

    Args:
        varname (str): Name of the variable to look up
        fallback (str): A fallback value if ``varname`` does not exist
    Raises:
        PreconditionError: The variable does not exist and no fallback value
            was set
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
    ``get_user_env_var()`` to look up the substitution.

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
    ``get_user_env_var()`` to look up the substitution.

    Args:
        path (str): The path that will be expanded
    Returns:
        str: The expanded path
    """
    if path[0] == "~":
        path = get_user_env_var("HOME") + path[1:]
    return path


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

def import_profile_class(class_name):
    """Imports a profile class only by it's name.

    Searches ``constants.PROFILE_FILES`` for python modules and imports them
    temporarily. If the module has a class that is the same as ``class_name``
    it returns it.

    Args:
        class_name (str): The name of the class that will be imported
    Raises:
        GenerationError: One of the modules in contained
            ``constants.PROFILE_FILES`` errors or the imported class doesn't
            inherit from ``Profile``
        PreconditionError: No class with the provided name exists
    Returns:
        class: The class that was imported
    """
    # Import profile (can't be done globally because profile needs to
    # import this module first)
    from dotmanager.profile import Profile
    # Go through all files in the profile directory
    for root, _, files in os.walk(constants.PROFILE_FILES):
        for file in files:
            file = os.path.join(root, file)
            # Ignore everything that isn't a python module
            if file[-2:] != "py":
                break
            try:
                # Import module
                spec = importlib.util.spec_from_file_location("__name__", file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as err:
                raise GenerationError(class_name, "The module '" + file +
                                      "' contains an error and therefor " +
                                      "can't be imported. The error was:" +
                                      "\n   " + str(err))
            # Return the class if it is in this module
            if class_name in module.__dict__:
                tmp_class = module.__dict__[class_name]
                if issubclass(tmp_class, Profile):
                    return module.__dict__[class_name]
                msg = "The class '" + class_name + "' does not inherit from"
                msg += "Profile and therefore can't be imported."
                raise GenerationError(class_name, msg)
    raise PreconditionError("The profile '" + class_name +
                            "' could not be found in any module. Aborting.")


# Misc
###############################################################################

logger = logging.getLogger("root")

def get_date_time_now():
    """Returns a datetime string for the current moment in the format
    YYYY-MM-DD hh:mm:ss

    Returns:
        str: The datetime string
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_warning(message):
    """Prints text in warning color.

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.warning(constants.WARNING + message + constants.ENDC)


def log_success(message):
    """Prints text in success color

    Using the log functions, the output will also be printed into a logfile
    if the user set the ``--log`` flag.

    Args:
        message (str): The message that will be printed.
    """
    logger.debug(constants.OKGREEN + message + constants.ENDC)


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
        paths (List): A list of paths that will be searched for ``filename``
    Returns:
        List: A list of file paths that were found
    """
    return [os.path.join(path, filename) for path in paths
            if os.path.isfile(os.path.join(path, filename))]
