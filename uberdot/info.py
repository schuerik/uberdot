"""This module provides simple functions for users to
retrieve system information."""

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


import os
import re
import shutil
import platform
from uberdot.utils import get_current_username


def distribution():
    """Returns the current running distribution.

    Returns:
        str: Returns the first line of ``/etc/*-release``
    """
    for entry in os.listdir("/etc"):
        # search for release file
        if re.search(r"^\w+(-|_)release$", entry):
            line = open("/etc/" + entry, "r").readline()
            return line.split('"')[1]
    return None


def hostname():
    """Returns the host name of the device.

    Returns:
        str: The devices host name
    """
    return platform.node()


def is_64bit():
    """Returns if the device is running a 64bit os.

    Returns:
        bool: True, if platform is 64 bit
    """
    return platform.architecture()[0] == "64bit"


def kernel():
    """Returns the current kernel release of the device.

    The kernel release tells you what version of the kernel is currently
    used.

    Returns:
        str: The kernel release of the device
    """
    return platform.release()


def pkg_installed(pkg_name):
    """Returns if the given package is installed on the device.

    Args:
        pkg_name (str): The name of a package

    Returns:
        bool: True, if installed
    """
    return bool(shutil.which(pkg_name))


def username():
    """Returns the username of the user that executed uberdot.

    Returns:
        str: Username of current user
    """
    return get_current_username()
