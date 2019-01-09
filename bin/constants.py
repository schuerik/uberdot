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
from bin.utils import normpath

# Init config file
configfile = os.path.dirname(os.path.dirname(sys.modules[__name__].__file__))
configfile = os.path.join(configfile, "data/dotmanager.ini")
config = configparser.ConfigParser()
config.read(configfile)


# Constants below can be used immediatly after importing this module
###############################################################################

# Colors
if config.getboolean("Settings", "color", fallback=True):
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    NOBOLD = '\033[22m'
else:
    OKGREEN = WARNING = FAIL = ENDC = BOLD = UNDERLINE = NOBOLD = ''

# Defaults for options
DUISTRATEGY = config.getboolean("Arguments", "duiStrategy", fallback=False)
FORCE = config.getboolean("Arguments", "force", fallback=False)
VERBOSE = config.getboolean("Arguments", "verbose", fallback=False)
MAKEDIRS = config.getboolean("Arguments", "makeDirs", fallback=False)

# Default decryption password
DECRYPT_PWD = config.get("Settings", "decryptPwd", fallback=None)

# Version numbers, seperated by underscore. First part is the version of
# the manager. The second part (after the underscore) is the version of
# the installed-file schema.
VERSION = "1.6.0_3"


# Constants below must be loaded first before using them
###############################################################################

# File paths
BACKUP_EXTENSION = config.get("Settings", "backupExtension", fallback="bak")
INSTALLED_FILE = "data/installed/%s.json"
INSTALLED_FILE_BACKUP = INSTALLED_FILE + "." + BACKUP_EXTENSION
PROFILE_FILES = config.get("Settings", "profileFiles", fallback="profiles")
TARGET_FILES = config.get("Settings", "targetFiles", fallback="files")

# Profile defaults
DEFAULTS = {}
DIR_DEFAULT = ""

# Defaults from the config. If not set in config a fallback is provided.
# This is then used as fallback for all further values loaded from the config.
FALLBACK = {
    "directory": config.get("DEFAULTS", "directory", fallback="$HOME"),
    "name": config.get("DEFAULTS", "name", fallback=""),
    "optional": config.getboolean("DEFAULTS", "optional", fallback=False),
    "owner": config.get("DEFAULTS", "owner", fallback=""),
    "permission": config.getint("DEFAULTS", "permission", fallback=644),
    "prefix": config.get("DEFAULTS", "prefix", fallback=""),
    "preserve_tags": config.getboolean("DEFAULTS", "preserve_tags",
                                       fallback=False),
    "replace": config.get("DEFAULTS", "replace", fallback=""),
    "replace_pattern": config.get("DEFAULTS", "replace_pattern", fallback=""),
    "suffix": config.get("DEFAULTS", "suffix", fallback="")
}


def load_constants(installed_filename: str) -> None:
    """Load constants/defaults according to the INSTALLED-FILE used"""
    global DEFAULTS, DIR_DEFAULT, INSTALLED_FILE, INSTALLED_FILE_BACKUP
    global TARGET_FILES, PROFILE_FILES
    name = "Installed." + installed_filename
    # Load defaults from the corresponding section of the config
    DEFAULTS = {
        "name": config.get(name, "name", fallback=FALLBACK["name"]),
        "optional": config.getboolean(name, "optional",
                                      fallback=FALLBACK["optional"]),
        "owner": config.get(name, "owner", fallback=FALLBACK["owner"]),
        "permission": config.getint(name, "permission",
                                    fallback=FALLBACK["permission"]),
        "prefix": config.get(name, "prefix", fallback=FALLBACK["prefix"]),
        "preserve_tags": config.getboolean(name, "preserve_tags",
                                           fallback=FALLBACK["preserve_tags"]),
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
