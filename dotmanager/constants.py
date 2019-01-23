"""Provides constants, defaults and the ability to load configs or
overwrite defaults for a specific configuration"""

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


import configparser
import csv
import os
import sys
from dotmanager.errors import PreconditionError
from dotmanager.types import Path
from dotmanager.utils import find_files
from dotmanager.utils import get_user_env_var
from dotmanager.utils import normpath

# Search paths for config files
CONFIG_SEARCH_PATHS = [
    os.path.join(
        os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
        "data"
    ),
    "/etc/dotmanager",
    os.path.join(
        get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
        "dotmanager"
    )
]

# Version numbers, seperated by underscore. First part is the version of
# the manager. The second part (after the underscore) is the version of
# the installed-file schema.
VERSION = "1.6.8_3"


# Setting defaults/fallback values for all constants
###############################################################################

# Arguments
DUISTRATEGY = False
FORCE = False
VERBOSE = False
MAKEDIRS = False

# Settings
COLOR = True
DECRYPT_PWD = None
BACKUP_EXTENSION = "bak"
PROFILE_FILES = "profiles"
TARGET_FILES = "files"

# Internal values
INSTALLED_FILE = "data/installed/%s.json"
INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
DIR_DEFAULT = ""
FALLBACK = {
    "directory": "$HOME",
    "name": "",
    "optional": False,
    "owner": "",
    "permission": 644,
    "prefix": "",
    "preserve_tags": False,
    "replace": "",
    "replace_pattern": "",
    "suffix": ""
}
DEFAULTS = dict(FALLBACK)
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
NOBOLD = '\033[22m'


# Loaders for config and installed-section
###############################################################################

def loadconfig(config_file: Path, installed_filename: str = "default") -> None:
    """Loads a config file from a given path.
    Falls back to default if no path was provided"""
    global OKGREEN, WARNING, FAIL, ENDC, BOLD, UNDERLINE, NOBOLD
    global DUISTRATEGY, FORCE, VERBOSE, MAKEDIRS, DECRYPT_PWD
    global BACKUP_EXTENSION, PROFILE_FILES, TARGET_FILES, INSTALLED_FILE_BACKUP
    global COLOR, INSTALLED_FILE, DEFAULTS, DIR_DEFAULT, FALLBACK

    # Init config file
    cfg_files = find_files("dotmanager.ini", CONFIG_SEARCH_PATHS)

    if config_file:
        cfg_files.append(config_file)

    config = configparser.ConfigParser()

    try:
        for cfg in cfg_files:
            config.read(cfg)
    except configparser.Error as err:
        raise PreconditionError(f"Can't parse config. {err.message}")

    # Arguments
    DUISTRATEGY = config.getboolean("Arguments", "duiStrategy",
                                    fallback=DUISTRATEGY)
    FORCE = config.getboolean("Arguments", "force", fallback=FORCE)
    VERBOSE = config.getboolean("Arguments", "verbose", fallback=VERBOSE)
    MAKEDIRS = config.getboolean("Arguments", "makeDirs", fallback=MAKEDIRS)

    # Settings
    DECRYPT_PWD = config.get("Settings", "decryptPwd", fallback=DECRYPT_PWD)
    BACKUP_EXTENSION = config.get("Settings", "backupExtension",
                                  fallback=BACKUP_EXTENSION)
    PROFILE_FILES = config.get("Settings", "profileFiles",
                               fallback=PROFILE_FILES)
    TARGET_FILES = config.get("Settings", "targetFiles", fallback=TARGET_FILES)
    COLOR = config.getboolean("Settings", "color", fallback=COLOR)

    # Internal values
    INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
    if not COLOR:
        OKGREEN = WARNING = FAIL = ENDC = BOLD = UNDERLINE = NOBOLD = ''
    FALLBACK = {
        "directory": config.get("DEFAULTS", "directory",
                                fallback=FALLBACK["directory"]),
        "name": config.get("DEFAULTS", "name",
                           fallback=FALLBACK["name"]),
        "optional": config.getboolean("DEFAULTS", "optional",
                                      fallback=FALLBACK["optional"]),
        "owner": config.get("DEFAULTS", "owner",
                            fallback=FALLBACK["owner"]),
        "permission": config.getint("DEFAULTS", "permission",
                                    fallback=FALLBACK["permission"]),
        "prefix": config.get("DEFAULTS", "prefix",
                             fallback=FALLBACK["prefix"]),
        "replace": config.get("DEFAULTS", "replace",
                              fallback=FALLBACK["replace"]),
        "replace_pattern": config.get("DEFAULTS", "replace_pattern",
                                      fallback=FALLBACK["replace_pattern"]),
        "suffix": config.get("DEFAULTS", "suffix", fallback=FALLBACK["suffix"])
    }

    # Load defaults from the corresponding section of the config
    name = "Installed." + installed_filename
    DEFAULTS = {
        "name": config.get(name, "name", fallback=FALLBACK["name"]),
        "optional": config.getboolean(name, "optional",
                                      fallback=FALLBACK["optional"]),
        "owner": config.get(name, "owner", fallback=FALLBACK["owner"]),
        "permission": config.getint(name, "permission",
                                    fallback=FALLBACK["permission"]),
        "prefix": config.get(name, "prefix", fallback=FALLBACK["prefix"]),
        "replace": config.get(name, "replace", fallback=FALLBACK["replace"]),
        "replace_pattern": config.get(name, "replace_pattern",
                                      fallback=FALLBACK["replace_pattern"]),
        "suffix": config.get(name, "suffix", fallback=FALLBACK["suffix"])
    }
    DIR_DEFAULT = config.get(name, "directory", fallback=FALLBACK["directory"])
    DEFAULTS["tags"] = next(csv.reader([config.get(name, "tags",
                                                   fallback="")]))
    # Insert installed-file into constants
    INSTALLED_FILE = INSTALLED_FILE % installed_filename
    INSTALLED_FILE_BACKUP = INSTALLED_FILE_BACKUP % installed_filename

    # Normalize paths
    DIR_DEFAULT = normpath(DIR_DEFAULT)
    INSTALLED_FILE = normpath(INSTALLED_FILE)
    INSTALLED_FILE_BACKUP = normpath(INSTALLED_FILE_BACKUP)
    TARGET_FILES = normpath(TARGET_FILES)
    PROFILE_FILES = normpath(PROFILE_FILES)
