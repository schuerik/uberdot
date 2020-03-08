"""Provides constants, defaults and the ability to load configs or
overwrite defaults for a specific configuration."""

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


import configparser
import csv
import os
import sys
from copy import deepcopy
from uberdot.errors import PreconditionError
from uberdot.utils import find_files
from uberdot.utils import get_user_env_var
from uberdot.utils import get_username
from uberdot.utils import get_permission
from uberdot.utils import get_uid
from uberdot.utils import normpath

# TODO: doc & cleanup


############################################################################
# True hardcoded not loadable constants (not visible via --debuginfo)
############################################################################
VERSION = "1.17.0"
STATE_NAME = "state.json"
DATA_DIR_ROOT = "/root/.uberdot/"
DATA_DIR_TEMP = "/home/%s/.uberdot/"
SESSION_SUBDIR = "sessions/%s/"


############################################################################
# Not loadable, but flexible constants (only set on first import)
############################################################################
def gen_data_dir(user):
    if user == "root":
        path = DATA_DIR_ROOT
    else:
        path = DATA_DIR_TEMP % user
    return user, path

user = get_username(get_uid())
users = ["root"] + os.listdir("/home")
users.remove(user)
# Build/Prepare paths to stored data
if not os.getenv("UBERDOT_TEST", 0):
    data_dir = gen_data_dir(user)[1]
    data_dirs_foreign = list(map(gen_data_dir, users))
    data_dirs_foreign = list(
        filter(lambda x: os.path.exists(x[1]), data_dirs_foreign)
    )
else:
    # Using a dedicated data_dir that is tracked by git
    # so the tests can set back generated files and the logged state
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
        "test/regression/data/"
    )
    # simulating a second user "test"
    data_dirs_foreign = [
        ("test", os.path.join(os.path.dirname(data_dir), "data_test"))
    ]


############################################################################
# Initialize loadable constants with defaults
############################################################################

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


############################################################################
# Setup mainpulation functions
############################################################################
def __decode_ansi(string):
    return string.encode("utf-8").decode("unicode_escape")


############################################################################
# Initialize constants
############################################################################
values = {
    # name: (default value, configsection, type, manipulation function)
    "cfg_files"           : ([],                     None,        "list", None),
    "cfg_search_paths"    : (cfg_search_paths,       None,        "list", None),
    "changes"             : (False,                  None,        "bool", None),
    "col_endc"            : ('\x1b[0m',              None,        "str",  None),
    "debug"               : (False,                  None,        "bool", None),
    "debuginfo"           : (False,                  None,        "bool", None),
    "dryrun"              : (False,                  None,        "bool", None),
    "session_dir"         : (session_dir,            None,        "path", None),
    "session_dirs_foreign": (session_dirs_foreign,   None,        "list", None),
    "mode"                : ("",                     None,        "str",  None),
    "owd"                 : (os.getcwd(),            None,        "str",  None),
    "parent"              : (None,                   None,        "str",  None),
    "session"             : ("default",              None,        "str",  str.lower),
    "all"                 : (False,                  "Arguments", "bool", None),
    "allusers"            : (False,                  "Arguments", "bool", None),
    "content"             : (False,                  "Arguments", "bool", None),
    "dotfiles"            : (False,                  "Arguments", "bool", None),
    "dui"                 : (False,                  "Arguments", "bool", None),
    "filename"            : (False,                  "Arguments", "bool", None),
    "fix"                 : ("",                     "Arguments", "str",  None),
    "force"               : (False,                  "Arguments", "bool", None),
    "ignore"              : ([],                     "Arguments", "list", None),
    "ignorecase"          : (False,                  "Arguments", "bool", None),
    "links"               : (False,                  "Arguments", "bool", None),
    "logfile"             : ("",                     "Arguments", "path", None),
    "logginglevel"        : ("INFO",                 "Arguments", "str",  str.upper),
    "makedirs"            : (False,                  "Arguments", "bool", None),
    "meta"                : (False,                  "Arguments", "bool", None),
    "names"               : (True,                   "Arguments", "bool", None),
    "locations"           : (True,                   "Arguments", "bool", None),
    "profilenames"        : ([],                     "Arguments", "list", None),
    "profiles"            : (False,                  "Arguments", "bool", None),
    "regex"               : (False,                  "Arguments", "bool", None),
    "searchstr"           : ("",                     "Arguments", "str",  None),
    "searchtags"          : (False,                  "Arguments", "bool", None),
    "short"               : (False,                  "Arguments", "bool", None),
    "skipafter"           : (False,                  "Arguments", "bool", None),
    "skipbefore"          : (False,                  "Arguments", "bool", None),
    "skipevents"          : (False,                  "Arguments", "bool", None),
    "skiproot"            : (False,                  "Arguments", "bool", None),
    "superforce"          : (False,                  "Arguments", "bool", None),
    "users"               : ([],                     "Arguments", "list", None),
    "askroot"             : (True,                   "Settings",  "bool", None),
    "backup_extension"    : ("bak",                  "Settings",  "str",  None),
    "color"               : (True,                   "Settings",  "bool", None),
    "col_emph"            : ('\x1b[1m',              "Settings",  "str",  __decode_ansi),
    "col_fail"            : ('\x1b[91m',             "Settings",  "str",  __decode_ansi),
    "col_ok"              : ('\x1b[92m',             "Settings",  "str",  __decode_ansi),
    "col_warning"         : ('\x1b[93m',             "Settings",  "str",  __decode_ansi),
    "col_debug"           : ('\x1b[90m',             "Settings",  "str",  __decode_ansi),
    "decrypt_pwd"         : (None,                   "Settings",  "str",  None),
    "hash_separator"      : ("#",                    "Settings",  "str",  None),
    "profile_files"       : ("",                     "Settings",  "path", None),
    "shell"               : ("/bin/bash",            "Settings",  "path", None),
    "shell_args"          : ("-e -O expand_aliases", "Settings",  "str",  None),
    "shell_timeout"       : (60,                     "Settings",  "int",  None),
    "smart_cd"            : (True,                   "Settings",  "bool", None),
    "tag_separator"       : ("%",                    "Settings",  "str",  None),
    "target_files"        : ("",                     "Settings",  "path", None),
    "directory"           : ("$HOME",                "Defaults",  "path", None),
    "extension"           : ("",                     "Defaults",  "str",  None),
    "name"                : ("",                     "Defaults",  "str",  None),
    "optional"            : (False,                  "Defaults",  "bool", None),
    "owner"               : ("",                     "Defaults",  "str",  None),
    "permission"          : (permission,             "Defaults",  "int",  None),
    "prefix"              : ("",                     "Defaults",  "str",  None),
    "replace"             : ("",                     "Defaults",  "str",  None),
    "replace_pattern"     : ("",                     "Defaults",  "str",  None),
    "secure"              : (True,                   "Defaults",  "bool", None),
    "suffix"              : ("",                     "Defaults",  "str",  None),
    "tags"                : ([],                     "Defaults",  "list", None),
}
defaults = dict(values)
# Make values easy accessible
for name, props in values.items():
    globals()[name] = props[0]


############################################################################
# Loading and helper function
############################################################################

def reset():
    global values
    values = dict(defaults)

def _set(name, value):
    global values
    val_props = values[name]
    if val_props[3] is not None:
        value = val_props[3](value)
    values[name] = value, val_props[1], val_props[2], val_props[3]
    # Upate global field
    globals()[name] = value

def get(name):
    return deepcopy(values[name][0])

def vals():
    return [
        (item[1], key) for key, item in values.items()
    ]

def items(section=None):
    return [
        (key, item[0]) for key, item in values.items()
        if section is None or section == item[1]
    ]

def load(args):
    # Find all configs
    cfgs = find_files("uberdot.ini", get("cfg_search_paths"))
    if args.config:
       cfgs += [os.path.join(get("owd"), args.config)]
    _set("cfg_files", cfgs)
    if args.session:
        _set("session", args.session)
    # Load configs
    config = configparser.ConfigParser()
    try:
        for cfg in cfgs:
            config.read(cfg)
            # We need to normalize all paths here, relatively to
            # the config file which it defined
            path_values = [
                "directory", "profile_files", "target_files", "logfile"
            ]
            for section in config.sections():
                for name, value in config.items(section):
                    if name in path_values:
                        config[section][name] = os.path.normpath(
                            os.path.join(os.path.dirname(cfg), value)
                        )
    except configparser.Error as err:
        msg = "Can't parse config at '" + cfg + "'. " + err.message
        raise PreconditionError(msg)
    # Write all values from config
    for name, props in values.items():
        # Skip all values don't belong to any section in the config file
        if props[1] is None:
            continue
        # Set getter for config depending on value type
        getter = config.get
        if props[2] == "int":
            getter = config.getint
        elif props[2] == "bool":
            getter = config.getboolean
        # Get value from config. Prefer values from special session section
        section = "Session." + get("session") + "." + props[1]
        if config.has_section(section) and config.has_option(section, name):
            value = getter(section, name)
        elif config.has_section(props[1]) and config.has_option(props[1], name):
            value = getter(props[1], name)
        else:
            # Value is not in config, skipping
            continue
        # Fix values depending on value type
        if props[2] == "list":
            value = next(csv.reader([value]))
        _set(name, value)

    # Remove all colors if disabled
    if not get("color"):
        for key, val in items():
            if key.startswith("col_"):
                _set(key, "")

    # Write arguments
    for arg, value in vars(args).items():
        if value is None or arg in ["config", "session"]:
            continue
        name = arg
        # Parse tags and set values for --options
        if arg == "opt_dict":
            if "tags" in value:
                value["tags"] = next(csv.reader([value["tags"]]))
            for key, val in value.items():
                _set(key, val)
            continue
        # Relative paths need to be absolute
        if arg in ["directory", "log"]:
            value = os.path.join(get("owd"), value)
        # Little fixes for arguments where the names don't match up
        # with the configuration file argument
        if arg == "log":
            name = "logfile"
        elif arg in ["verbose", "info", "quiet", "silent"]:
            if value:
                name = "logginglevel"
                value = arg
            else:
                continue
        elif arg == "tags":
            name = "searchtags"
        # Set argument
        _set(name, value)
    # Update internal values that depend on a loaded config
    _set("session_dir", get("session_dir") % get("session"))
    _set("session_dirs_foreign",
         list(map(
             lambda x: (x[0], x[1] % get("session")),
             session_dirs_foreign
         ))
     )
