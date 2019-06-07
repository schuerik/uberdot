"""Provides constants, defaults and the ability to load configs or
overwrite defaults for a specific configuration."""

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


import configparser
import csv
import os
import sys
from dotmanager.errors import PreconditionError
from dotmanager.errors import UserError
from dotmanager.utils import find_files
from dotmanager.utils import get_user_env_var
from dotmanager.utils import normpath

VERSION = "1.10.5_3"
"""Version numbers, seperated by underscore.

First part is the version of Dotmanager. The second part (after the underscore)
is the version of the installed-file schema. The latter will be used to
determine compability of the Dotmanager with the installed-file."""


# Setting defaults/fallback values for all constants
###############################################################################

# Arguments
DUISTRATEGY = False
"""True, if --dui should be set as default. Default is ``False``."""
FORCE = False
"""True, if --force should be set as default. Default is ``False``."""
MAKEDIRS = False
"""True, if Dotmanager shall create directories if they don't exist.
Default is ``False``.
"""
SUPERFORCE = False
"""True, if Dotmanager shall overwrite files that are blacklisted.
Default is ``False``.
"""


# Settings
LOGGINGLEVEL = "info"
"""The current logger level. Default is ``info``."""
LOGFILE = ""
"""The file that will be used as logfile. Empty if no logfile will be used.
Needs to be normalized before usage. Default is ``""``.
"""
COLOR = True
"""True, if output should be colored. Default is ``True``."""
DECRYPT_PWD = None
"""Contains the decryption password in plain text"""
BACKUP_EXTENSION = "bak"
"""The extension that will be used for backup files. Default is ``bak``."""
PROFILE_FILES = ""
"""The directory the profile will be loaded from"""
TARGET_FILES = ""
"""The directory the target files are located"""

# Internal values
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
    "data"
)
"""The path to the data directory"""
INSTALLED_FILE = os.path.join(DATA_DIR, "installed/%s.json")
"""The path to the installed-file that will be used for comparison"""
INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
"""The path to the file that will be used as backup of the installed-file"""
DIR_DEFAULT = "$HOME"
"""The default path that profiles start in"""
DEFAULTS = {
    "name": "",
    "optional": False,
    "owner": "",
    "permission": 644,
    "prefix": "",
    "replace": "",
    "replace_pattern": "",
    "suffix": ""
}
"""Default values for command options"""
OKGREEN = '\033[92m'
"""Bash color code for green text"""
WARNING = '\033[93m'
"""Bash color code for yellow text"""
FAIL = '\033[91m'
"""Bash color code for red text"""
ENDC = '\033[0m'
"""Bash color code to stop formatation of text"""
BOLD = '\033[1m'
"""Bash color code for bold text"""
UNDERLINE = '\033[4m'
"""Bash color code for underlined text"""
NOBOLD = '\033[22m'
"""Bash color code to stop bold text"""


# Loaders for config and installed-section
###############################################################################

# Search paths for config files
CFG_FILES = []
"""A list with all configuration files that will be used to set constants. All
settings of all configuration files will be used. If a specific setting is set
in more than one configuration file, the setting from the configuration file
with higher index will be prefered.
"""
CONFIG_SEARCH_PATHS = [
    "/etc/dotmanager",
    os.path.join(
        get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
        "dotmanager"
    ),
    DATA_DIR
]
"""A list of paths that will be used to search for configuration files. """


def loadconfig(config_file, installed_filename="default"):
    """Loads constants from the config files.

    This will load all configs from `CFG_FILES` or `config_file` if provided.
    The name of the installed-file will be used to load installed-file specific
    values.

    Args:
        config_file (str): Absolute path to the config file to use. If None,
            the configs from `CFG_FILES` will be loaded.
        installed_filename (str): Name of the installed-file for that values
            will be loaded
    """
    global OKGREEN, WARNING, FAIL, ENDC, BOLD, UNDERLINE, NOBOLD
    global DUISTRATEGY, FORCE, LOGGINGLEVEL, MAKEDIRS, DECRYPT_PWD, SUPERFORCE
    global BACKUP_EXTENSION, PROFILE_FILES, TARGET_FILES, INSTALLED_FILE_BACKUP
    global COLOR, INSTALLED_FILE, DEFAULTS, DIR_DEFAULT, LOGFILE, CFG_FILES

    # Load config files
    if config_file:
        CFG_FILES = [config_file]
    else:
        CFG_FILES = find_files("dotmanager.ini", CONFIG_SEARCH_PATHS)
    config = configparser.ConfigParser()
    try:
        for cfg in CFG_FILES:
            config.read(cfg)
    except configparser.Error as err:
        msg = "Can't parse config at '" + cfg + "'. " + err.message
        raise PreconditionError(msg)

    # Setup special lookup function for getting values
    def getvalue(getter, section):
        """Creates function to lookup a specific value in a specific section
        with a specific getter.

        Args:
            getter (Callable): getter function to perform a single lookup
            section (str): The section that contains the key
        Returns:
            function: A function that can lookup keys in the config
        """
        def lookup(key, fallback=None):
            """Looks up a value in a specific section for a specific type.

            Args:
                key (str): The name of the value that will be looked up
                fallback: A fallback value
            Returns:
                The value of the key
            """
            installedfile_section = "Installed." + installed_filename
            installedfile_section += "." + section
            value = getter(section, key, fallback=fallback)
            return getter(installedfile_section, key, fallback=value)
        return lookup

    # Get arguments
    getstr = getvalue(config.get, "Arguments")
    getbool = getvalue(config.getboolean, "Arguments")
    DUISTRATEGY = getbool("dui", DUISTRATEGY)
    FORCE = getbool("force", FORCE)
    MAKEDIRS = getbool("makedirs", MAKEDIRS)
    SUPERFORCE = getbool("superforce", SUPERFORCE)
    LOGGINGLEVEL = getstr("logginglevel", LOGGINGLEVEL).upper()
    LOGFILE = getstr("logfile", LOGFILE)

    # Get settings
    getstr = getvalue(config.get, "Settings")
    getbool = getvalue(config.getboolean, "Settings")
    DECRYPT_PWD = getstr("decryptPwd", DECRYPT_PWD)
    BACKUP_EXTENSION = getstr("backupExtension", BACKUP_EXTENSION)
    PROFILE_FILES = getstr("profileFiles")
    TARGET_FILES = getstr("targetFiles")
    COLOR = getbool("color", COLOR)

    # Setup internal values
    INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
    if not COLOR:
        OKGREEN = WARNING = FAIL = ENDC = BOLD = UNDERLINE = NOBOLD = ''

    # Get command options
    getstr = getvalue(config.get, "Defaults")
    getbool = getvalue(config.getboolean, "Defaults")
    getint = getvalue(config.getint, "Defaults")
    DEFAULTS = {
        "name": getstr("name", DEFAULTS["name"]),
        "optional": getbool("optional", DEFAULTS["optional"]),
        "owner": getstr("owner", DEFAULTS["owner"]),
        "permission": getint("permission", DEFAULTS["permission"]),
        "prefix": getstr("prefix", DEFAULTS["prefix"]),
        "replace": getstr("replace", DEFAULTS["replace"]),
        "replace_pattern": getstr("replace_pattern",
                                  DEFAULTS["replace_pattern"]),
        "suffix": getstr("suffix", DEFAULTS["suffix"]),
        "tags": next(csv.reader([getstr("tags", "")]))
    }
    DIR_DEFAULT = getstr("directory", DIR_DEFAULT)

    # Insert installed-file into constants
    INSTALLED_FILE = INSTALLED_FILE % installed_filename
    INSTALLED_FILE_BACKUP = INSTALLED_FILE_BACKUP % installed_filename

    # Check if TARGET_FILES and PROFILE_FILES were set by the user
    if not TARGET_FILES or TARGET_FILES == "</path/to/your/dotfiles/>":
        raise UserError("No directory for your dotfiles specified.")
    if not PROFILE_FILES or PROFILE_FILES == "</path/to/your/profiles/>":
        raise UserError("No directory for your profiles specified.")

    # Normalize paths
    DIR_DEFAULT = normpath(DIR_DEFAULT)
    TARGET_FILES = normpath(TARGET_FILES)
    PROFILE_FILES = normpath(PROFILE_FILES)
