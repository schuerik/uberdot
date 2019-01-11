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


import datetime
import importlib.util
import os
import pwd
import re
import subprocess
from typing import List
from typing import Optional
from typing import Tuple
from dotmanager import constants
from dotmanager.types import Path
from dotmanager.types import RelPath
from dotmanager.errors import FatalError
from dotmanager.errors import GenerationError
from dotmanager.errors import PreconditionError


# Utils for finding targets
###############################################################################

def find_target(target: str, tags: List[str]) -> Optional[Path]:
    """Find the correct target version in the repository to link to"""
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


def find_exact_target(target: str) -> Optional[Path]:
    """Find the exact target in the repository to link to"""
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
    elif not targets:
        # Ooh, nothing found
        return None
    # Return found target
    return targets[0]


def walk_dotfiles() -> List[Tuple[Path, str]]:
    """Returns a list of all dotfiles as tuple of directory and filename"""
    # load ignore list
    ignorelist_path = os.path.join(constants.TARGET_FILES, ".dotignore")
    if os.path.exists(ignorelist_path):
        with open(ignorelist_path, "r") as file:
            ignorelist = file.readlines()
        ignorelist = [entry.strip() for entry in ignorelist]
    else:
        ignorelist = []
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

def get_uid() -> None:
    """Get real users id"""
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        return int(sudo_uid)
    return os.getuid()


def get_gid() -> None:
    """Get real users group id"""
    sudo_gid = os.environ.get('SUDO_GID')
    if sudo_gid:
        return int(sudo_gid)
    return os.getgid()


def get_dir_owner(filename: Path) -> Tuple[int, int]:
    """Gets the owner of the directory of filename.
    Works even for directories that doesn't exist"""
    dirname = os.path.dirname(filename)
    while not os.path.isdir(dirname):
        dirname = os.path.dirname(dirname)
    return os.stat(dirname).st_uid, os.stat(dirname).st_gid


def has_root_priveleges() -> None:
    """Check if this programm wasxecuted as root"""
    return os.geteuid() == 0


def get_current_username() -> None:
    """Get real users username"""
    return pwd.getpwuid(get_uid()).pw_name


def get_user_env_var(varname: str) -> str:
    """Lookup an environment variable. If executed as root, the
    envirionment variable of the real user is return"""
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
            msg = "There is no environment varibable set for user '"
            msg += get_current_username() + "' with the name: '"
            msg += varname + "'"
            raise PreconditionError(msg)
    # A normal user can access its own variables
    try:
        return os.environ[varname]
    except KeyError:
        raise PreconditionError("There is no environment varibable set " +
                                "with the name: '" + varname + "'")


def expandvars(path: RelPath) -> RelPath:
    """Behaves like the os.path.expandvars() but uses
    get_user_env_var() to look up the substitution"""
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


def expanduser(path: RelPath) -> RelPath:
    """Behaves like the os.path.expanduser() but uses
    get_user_env_var() to look up the substitution"""
    if path[0] == "~":
        path = get_user_env_var("HOME") + path[1:]
    return path


def normpath(path: RelPath) -> Path:
    """Normalizes path, replaces ~ and environment vars,
    and converts it in an absolute path"""
    if path is not None:
        path = expandvars(path)
        path = expanduser(path)
        return os.path.abspath(path)
    return None


# Dynamic imports
###############################################################################

def import_profile_class(class_name: str) -> None:
    """This function imports a profile class only by it's name"""
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
                return module.__dict__[class_name]
    raise PreconditionError("The profile '" + class_name +
                            "' could not be found in any module. Aborting.")


# Misc
###############################################################################


def get_date_time_now() -> None:
    """Returns a datetime string for the current moment"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_warning(message: str) -> None:
    """Prints text in warning color"""
    print(constants.WARNING + message + constants.ENDC)


def print_success(message: str) -> None:
    """Prints text in success color"""
    print(constants.OKGREEN + message + constants.ENDC)


def is_dynamic_file(target: Path) -> bool:
    """Returns if a given path is a dynamic file"""
    return os.path.dirname(os.path.dirname(target)) == normpath("data")

def find_files(filename: str, paths: List[str]):
    """finds existing files matching filename in the paths"""
    return [path for path in paths if os.path.isfile(os.path.join(path, filename))]
