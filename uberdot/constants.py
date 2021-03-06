"""Provides constants, defaults and the ability to load configs or
overwrite defaults for a specific configuration."""

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


import configparser
import csv
import os
import sys
from uberdot.errors import PreconditionError
from uberdot.errors import UserError
from uberdot.utils import find_files
from uberdot.utils import get_user_env_var
from uberdot.utils import normpath

VERSION = "1.13.2_4"

"""Version numbers, seperated by underscore.

First part is the version of uberdot. The second part (after the underscore)
is the version of the installed-file schema. The latter will be used to
determine compability of the uberdot with the installed-file."""


# Setting defaults/fallback values for all constants
###############################################################################

# Arguments
DUISTRATEGY = False
"""True, if --dui should be set as default. Default is ``False``."""
FORCE = False
"""True, if --force should be set as default. Default is ``False``."""
MAKEDIRS = False
"""True, if uberdot shall create directories if they don't exist.
Default is ``False``.
"""
SKIPAFTER = False
"""True, if all operations shall be ignored by EventAfterInterpreters.
Default is ``False``.
"""
SKIPBEFORE = False
"""True, if all operations shall be ignored by EventBeforeInterpreters.
Default is ``False``.
"""
SKIPEVENTS = False
"""True, if all operations shall be ignored by EventInterpreters.
Default is ``False``.
"""
SKIPROOT = False
"""True, if all operations that requiere root permission shall be omitted.
Default is ``False``.
"""
SUPERFORCE = False
"""True, if uberdot shall overwrite files that are blacklisted.
Default is ``False``.
"""

# Settings
ASKROOT = True
"""True, if uberdot shall ask for root permission if needed. If False,
uberdot will fail if root permission is needed. Default is ``True``.
"""
LOGGINGLEVEL = "info"
"""The current logging level. Default is ``info``."""
LOGFILE = ""
"""The file that will be used as logfile. Empty if no logfile will be used.
Needs to be normalized before usage. Default is ``""``.
"""
SHELL = "/bin/bash"
"""The shell that is used to execute event callbacks."""
SHELL_ARGS = "-e -O expand_aliases"
"""The arguments that will be passed to the shell."""
SHELL_TIMEOUT = 60
"""Time in seconds that a shell command is allowed to run without
printing something out."""
COLOR = True
"""True, if output should be colored. Default is ``True``."""
DECRYPT_PWD = None
"""Contains the decryption password in plain text."""
BACKUP_EXTENSION = "bak"
"""The extension that will be used for backup files. Default is ``bak``."""
TAG_SEPARATOR = "%"
"""The symbol that is used as separator for tags in dotfile names."""
HASH_SEPARATOR = "#"
"""The symbol that is used as separator for hashes in dynamic file names."""
PROFILE_FILES = ""
"""The directory where the profile will be loaded from."""
TARGET_FILES = ""
"""The directory where the dotfiles are located."""
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
    "data"
)
"""The directory that stores installed-files, dynamic files and
some static files."""
SMART_CD = True
"""True, if event shell scripts shall automatically change the directory
to the directory of the profile that triggered the event."""

# Internal values
"""The path to the data directory."""
INSTALLED_FILE = os.path.join(DATA_DIR, "installed/%s.json")
"""The path to the installed-file that will be used for comparison."""
INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
"""The path to the file that will be used as backup of the installed-file."""
DIR_DEFAULT = "$HOME"
"""The default path that profiles start in."""
DEFAULTS = {
    "extension": "",
    "name": "",
    "optional": False,
    "owner": "",
    "permission": 644,
    "prefix": "",
    "replace": "",
    "replace_pattern": "",
    "secure": True,
    "suffix": ""
}
"""Default values for command options."""
C_OK = '\033[92m'
"""Bash color code for successful output (green)."""
C_WARNING = '\033[93m'
"""Bash color code for warning output (yellow)."""
C_FAIL = '\033[91m'
"""Bash color code for error output (red)."""
C_HIGHLIGHT = '\033[34m'
"""Bash color code for highlighting normal output (blue)."""
C_DEBUG = '\033[90m'
"""Bash color code for debugging output (gray)."""
ENDC = '\033[0m'
"""Bash color code to stop formatation of text."""
BOLD = '\033[1m'
"""Bash color code for bold text."""
NOBOLD = '\033[22m'
"""Bash color code to stop bold text."""


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
    "/etc/uberdot",
    os.path.join(
        get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
        "uberdot"
    ),
    DATA_DIR
]
"""A list of paths that will be used to search for configuration files. """


def loadconfig(config_file, installed_filename="default"):
    """Loads constants from the config files.

    This will load all configs from :const:`CFG_FILES` or ``config_file``
    if provided. The name of the installed-file will be used to load
    installed-file specific values.

    Args:
        config_file (str): Absolute path to the config file to use. If None,
            the configs from :const:`CFG_FILES` will be loaded.
        installed_filename (str): Name of the installed-file for that values
            will be loaded
    """
    global C_OK, C_WARNING, C_FAIL, ENDC, BOLD, C_HIGHLIGHT, NOBOLD, C_DEBUG
    global DUISTRATEGY, FORCE, LOGGINGLEVEL, MAKEDIRS, DECRYPT_PWD, SUPERFORCE
    global SKIPROOT, DATA_DIR, SHELL, SHELL_TIMEOUT, SMART_CD, SKIPEVENTS
    global BACKUP_EXTENSION, PROFILE_FILES, TARGET_FILES, INSTALLED_FILE_BACKUP
    global COLOR, INSTALLED_FILE, DEFAULTS, DIR_DEFAULT, LOGFILE, CFG_FILES
    global ASKROOT, TAG_SEPARATOR, HASH_SEPARATOR, SKIPAFTER, SKIPBEFORE
    global SHELL_ARGS

    # Load config files
    if config_file:
        CFG_FILES = [config_file]
    else:
        CFG_FILES = find_files("uberdot.ini", CONFIG_SEARCH_PATHS)
    config = configparser.ConfigParser()
    try:
        for cfg in CFG_FILES:
            config.read(cfg)
            # We need to normalize all paths here, relatively to
            # the config file which it defined
            path_keys = [
                "directory", "profilefiles", "targetfiles",
                "logfile", "datadir"
            ]
            for section in config.sections():
                for item in config.items(section):
                    key = item[0]
                    if key in path_keys:
                        config[section][key] = os.path.join(
                            os.path.dirname(cfg), config[section][key]
                        )
                        config[section][key] = os.path.normpath(
                            config[section][key]
                        )
    except configparser.Error as err:
        msg = "Can't parse config at '" + cfg + "'. " + err.message
        raise PreconditionError(msg)

    # Setup special lookup function for getting values
    def getvalue(getter, section):
        """Creates function to lookup a specific value in a specific section
        with a specific getter.

        Args:
            getter (function): getter function to perform a single lookup
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
    SKIPAFTER = getbool("skipafter", SKIPAFTER)
    SKIPBEFORE = getbool("skipbefore", SKIPBEFORE)
    SKIPEVENTS = getbool("skipevents", SKIPEVENTS)
    SKIPROOT = getbool("skiproot", SKIPROOT)
    SUPERFORCE = getbool("superforce", SUPERFORCE)
    LOGGINGLEVEL = getstr("logginglevel", LOGGINGLEVEL).upper()
    LOGFILE = getstr("logfile", LOGFILE)

    # Get settings
    getstr = getvalue(config.get, "Settings")
    getbool = getvalue(config.getboolean, "Settings")
    getint = getvalue(config.getint, "Settings")
    ASKROOT = getbool("askroot", ASKROOT)
    SHELL = getstr("shell", SHELL)
    SHELL_ARGS = getstr("shellArgs", SHELL_ARGS)
    SHELL_TIMEOUT = getint("shellTimeout", SHELL_TIMEOUT)
    DECRYPT_PWD = getstr("decryptPwd", DECRYPT_PWD)
    BACKUP_EXTENSION = getstr("backupExtension", BACKUP_EXTENSION)
    TAG_SEPARATOR = getstr("tagSeparator", TAG_SEPARATOR)
    HASH_SEPARATOR = getstr("hashSeparator", HASH_SEPARATOR)
    PROFILE_FILES = getstr("profileFiles")
    TARGET_FILES = getstr("targetFiles")
    DATA_DIR = normpath(getstr("dataDir", DATA_DIR))
    COLOR = getbool("color", COLOR)
    SMART_CD = getbool("smartShellCWD", SMART_CD)

    # Setup internal values
    INSTALLED_FILE = os.path.join(DATA_DIR, "installed/%s.json")
    INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
    if not COLOR:
        C_OK = C_WARNING = C_FAIL = ENDC = BOLD = C_HIGHLIGHT = NOBOLD = ''
        C_DEBUG = ''

    # Get command options
    getstr = getvalue(config.get, "Defaults")
    getbool = getvalue(config.getboolean, "Defaults")
    getint = getvalue(config.getint, "Defaults")
    DEFAULTS = {
        "extension": getstr("extension", DEFAULTS["extension"]),
        "name": getstr("name", DEFAULTS["name"]),
        "optional": getbool("optional", DEFAULTS["optional"]),
        "owner": getstr("owner", DEFAULTS["owner"]),
        "permission": getint("permission", DEFAULTS["permission"]),
        "prefix": getstr("prefix", DEFAULTS["prefix"]),
        "replace": getstr("replace", DEFAULTS["replace"]),
        "replace_pattern": getstr("replace_pattern",
                                  DEFAULTS["replace_pattern"]),
        "suffix": getstr("suffix", DEFAULTS["suffix"]),
        "secure": getbool("secure", DEFAULTS["secure"]),
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
