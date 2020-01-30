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
from uberdot.utils import find_files
from uberdot.utils import get_user_env_var
from uberdot.utils import normpath

# TODO: doc

############################################################################
# Initialize constants with defaults
############################################################################

owd = os.getcwd()
data_dir = os.path.join(
    os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
    "data"
)
installed_path_template = "installed/%s.json"
installed = os.path.join(data_dir, installed_path_template)
searchpaths = [
    "/etc/uberdot",
    os.path.join(
        get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
        "uberdot"
    ),
    data_dir
]
f = False  # I just want to get some space in the datastructure below
values = {
    # name: (value, was_overwritten, configsection, type, manipulation function)
    "cfg_files"       : ([],                     f, None,        "list", None),
    "cfg_search_paths": (searchpaths,            f, None,        "list", None),
    "col_bold"        : ('\033[1m',              f, None,        "str",  None),
    "col_endc"        : ('\033[0m',              f, None,        "str",  None),
    "col_fail"        : ('\033[91m',             f, None,        "str",  None),
    "col_nobold"      : ('\033[22m',             f, None,        "str",  None),
    "col_ok"          : ('\033[92m',             f, None,        "str",  None),
    "col_warning"     : ('\033[93m',             f, None,        "str",  None),
    "col_debug"       : ('\033[90m',             f, None,        "str",  None),
    "debuginfo"       : (False,                  f, None,        "bool", None),
    "dryrun"          : (False,                  f, None,        "bool", None),
    "installed_file"  : (installed,              f, None,        "str",  None),
    "installed_backup": ("",                     f, None,        "str",  None),
    "mode"            : ("",                     f, None,        "str",  None),
    "owd"             : (owd,                    f, None,        "str",  None),
    "parent"          : (None,                   f, None,        "str",  None),
    "plain"           : (False,                  f, None,        "str",  None),
    "print"           : (False,                  f, None,        "str",  None),
    "version"         : ("1.12.17_4",            f, None,        "str",  None),
    "all"             : (False,                  f, "Arguments", "bool", None),
    "content"         : (False,                  f, "Arguments", "bool", None),
    "dotfiles"        : (False,                  f, "Arguments", "bool", None),
    "dui"             : (False,                  f, "Arguments", "bool", None),
    "filename"        : (False,                  f, "Arguments", "bool", None),
    "force"           : (False,                  f, "Arguments", "bool", None),
    "ignore"          : ([],                     f, "Arguments", "list", None),
    "ignorecase"      : (False,                  f, "Arguments", "bool", None),
    "links"           : (False,                  f, "Arguments", "bool", None),
    "logfile"         : ("",                     f, "Arguments", "path", None),
    "logginglevel"    : ("INFO",                 f, "Arguments", "str",  str.upper),
    "makedirs"        : (False,                  f, "Arguments", "bool", None),
    "meta"            : (False,                  f, "Arguments", "bool", None),
    "names"           : (True,                   f, "Arguments", "bool", None),
    "locations"       : (True,                   f, "Arguments", "bool", None),
    "profilenames"    : ([],                     f, "Arguments", "list", None),
    "profiles"        : (False,                  f, "Arguments", "bool", None),
    "regex"           : (False,                  f, "Arguments", "bool", None),
    "save"            : ("default",              f, "Arguments", "str",  str.lower),
    "searchstr"       : ("",                     f, "Arguments", "str",  None),
    "searchtags"      : (False,                  f, "Arguments", "bool", None),
    "skipafter"       : (False,                  f, "Arguments", "bool", None),
    "skipbefore"      : (False,                  f, "Arguments", "bool", None),
    "skipevents"      : (False,                  f, "Arguments", "bool", None),
    "skiproot"        : (False,                  f, "Arguments", "bool", None),
    "superforce"      : (False,                  f, "Arguments", "bool", None),
    "askroot"         : (True,                   f, "Settings",  "bool", None),
    "backup_extension": ("bak",                  f, "Settings",  "str",  None),
    "color"           : (True,                   f, "Settings",  "bool", None),
    "data_dir"        : (data_dir,               f, "Settings",  "str",  None),
    "decrypt_pwd"     : (None,                   f, "Settings",  "str",  None),
    "hash_separator"  : ("#",                    f, "Settings",  "str",  None),
    "profile_files"   : ("",                     f, "Settings",  "path", None),
    "shell"           : ("/bin/bash",            f, "Settings",  "path", None),
    "shell_args"      : ("-e -O expand_aliases", f, "Settings",  "str",  None),
    "shell_timeout"   : (60,                     f, "Settings",  "int",  None),
    "smart_cd"        : (True,                   f, "Settings",  "bool", None),
    "tag_separator"   : ("%",                    f, "Settings",  "str",  None),
    "target_files"    : ("",                     f, "Settings",  "path", None),
    "directory"       : ("$HOME",                f, "Defaults",  "path", None),
    "extension"       : ("",                     f, "Defaults",  "str",  None),
    "name"            : ("",                     f, "Defaults",  "str",  None),
    "optional"        : (False,                  f, "Defaults",  "bool", None),
    "owner"           : ("",                     f, "Defaults",  "str",  None),
    "permission"      : (644,                    f, "Defaults",  "int",  None),
    "prefix"          : ("",                     f, "Defaults",  "str",  None),
    "replace"         : ("",                     f, "Defaults",  "str",  None),
    "replace_pattern" : ("",                     f, "Defaults",  "str",  None),
    "secure"          : (True,                   f, "Defaults",  "bool", None),
    "suffix"          : ("",                     f, "Defaults",  "str",  None),
    "tags"            : ([],                     f, "Defaults",  "list", None),
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
    try:
        val_props = values[name]
    except KeyError:
        raise ValueError("'" + name + "' needs to be defined as constant")
    if val_props[4] is not None:
        value = val_props[4](value)
    values[name] = value, True, val_props[2], val_props[3], val_props[4]
    # Upate global field
    globals()[name] = value

def get(name):
    return values[name][0]

def vals():
    return [
        (item[2], key) for key, item in values.items()
    ]

def items(section=None):
    return [
        (key, item[0]) for key, item in values.items()
        if section is None or section == item[2]
    ]

def load(args):
    # Write arguments
    for arg, value in vars(args).items():
        if value is None:
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
        if arg in ["directory", "config", "log"]:
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
        elif arg == "config":
            name = "cfg_files"
            value = [value]
        elif arg == "tags":
            name = "searchtags"
        # Set argument
        _set(name, value)
    # Update internal values
    cfgs = find_files("uberdot.ini", get("cfg_search_paths"))
    cfgs += get("cfg_files")
    _set("cfg_files", cfgs)
    # Load config
    config = configparser.ConfigParser()
    try:
        for cfg in cfgs:
            config.read(cfg)
            # We need to normalize all paths here, relatively to
            # the config file which it defined
            path_values = [
                "directory", "profile_files", "target_files",
                "logfile", "data_dir"
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
        # Skip all values that are already overwritten by commandline
        # or don't belong to any section in the config file
        if props[1] or props[2] is None:
            continue
        # Set getter for config depending on value type
        getter = config.get
        if props[3] == "int":
            getter = config.getint
        elif props[3] == "bool":
            getter = config.getboolean
        # Get value from config. Prefer values from special installed section
        section = "Installed." + get("save") + "." + props[2]
        if config.has_section(section) and config.has_option(section, name):
            value = getter(section, name)
        elif config.has_section(props[2]) and config.has_option(props[2], name):
            value = getter(props[2], name)
        else:
            # Value is not in config, skipping
            continue
        # Fix values depending on value type
        if props[3] == "list":
            value = next(csv.reader([value]))
        _set(name, value)
    # Update internal values that depend on a loaded config
    installed_file = os.path.join(data_dir, installed_path_template) % get("save")
    installed_backup = installed_file + "." + get("backup_extension")
    _set("installed_file", installed_file)
    _set("installed_backup", installed_backup)
