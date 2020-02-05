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
values = {
    # name: (value, was_overwritten, configsection, type, manipulation function)
    "cfg_files"       : ([],                     None,        "list", None),
    "cfg_search_paths": (searchpaths,            None,        "list", None),
    "changes"         : (False,                  None,        "bool", None),
    "col_bold"        : ('\033[1m',              None,        "str",  None),
    "col_endc"        : ('\033[0m',              None,        "str",  None),
    "col_fail"        : ('\033[91m',             None,        "str",  None),
    "col_nobold"      : ('\033[22m',             None,        "str",  None),
    "col_ok"          : ('\033[92m',             None,        "str",  None),
    "col_warning"     : ('\033[93m',             None,        "str",  None),
    "col_debug"       : ('\033[90m',             None,        "str",  None),
    "debuginfo"       : (False,                  None,        "bool", None),
    "dryrun"          : (False,                  None,        "bool", None),
    "installed_file"  : (installed,              None,        "str",  None),
    "installed_backup": ("",                     None,        "str",  None),
    "mode"            : ("",                     None,        "str",  None),
    "owd"             : (owd,                    None,        "str",  None),
    "parent"          : (None,                   None,        "str",  None),
    "plain"           : (False,                  None,        "bool", None),
    "save"            : ("default",              None,        "str",  str.lower),
    "version"         : ("1.12.17_4",            None,        "str",  None),
    "all"             : (False,                  "Arguments", "bool", None),
    "content"         : (False,                  "Arguments", "bool", None),
    "dotfiles"        : (False,                  "Arguments", "bool", None),
    "dui"             : (False,                  "Arguments", "bool", None),
    "filename"        : (False,                  "Arguments", "bool", None),
    "force"           : (False,                  "Arguments", "bool", None),
    "ignore"          : ([],                     "Arguments", "list", None),
    "ignorecase"      : (False,                  "Arguments", "bool", None),
    "links"           : (False,                  "Arguments", "bool", None),
    "logfile"         : ("",                     "Arguments", "path", None),
    "logginglevel"    : ("INFO",                 "Arguments", "str",  str.upper),
    "makedirs"        : (False,                  "Arguments", "bool", None),
    "meta"            : (False,                  "Arguments", "bool", None),
    "names"           : (True,                   "Arguments", "bool", None),
    "locations"       : (True,                   "Arguments", "bool", None),
    "profilenames"    : ([],                     "Arguments", "list", None),
    "profiles"        : (False,                  "Arguments", "bool", None),
    "regex"           : (False,                  "Arguments", "bool", None),
    "searchstr"       : ("",                     "Arguments", "str",  None),
    "searchtags"      : (False,                  "Arguments", "bool", None),
    "skipafter"       : (False,                  "Arguments", "bool", None),
    "skipbefore"      : (False,                  "Arguments", "bool", None),
    "skipevents"      : (False,                  "Arguments", "bool", None),
    "skiproot"        : (False,                  "Arguments", "bool", None),
    "superforce"      : (False,                  "Arguments", "bool", None),
    "askroot"         : (True,                   "Settings",  "bool", None),
    "backup_extension": ("bak",                  "Settings",  "str",  None),
    "color"           : (True,                   "Settings",  "bool", None),
    "data_dir"        : (data_dir,               "Settings",  "str",  None),
    "decrypt_pwd"     : (None,                   "Settings",  "str",  None),
    "hash_separator"  : ("#",                    "Settings",  "str",  None),
    "profile_files"   : ("",                     "Settings",  "path", None),
    "shell"           : ("/bin/bash",            "Settings",  "path", None),
    "shell_args"      : ("-e -O expand_aliases", "Settings",  "str",  None),
    "shell_timeout"   : (60,                     "Settings",  "int",  None),
    "smart_cd"        : (True,                   "Settings",  "bool", None),
    "tag_separator"   : ("%",                    "Settings",  "str",  None),
    "target_files"    : ("",                     "Settings",  "path", None),
    "directory"       : ("$HOME",                "Defaults",  "path", None),
    "extension"       : ("",                     "Defaults",  "str",  None),
    "name"            : ("",                     "Defaults",  "str",  None),
    "optional"        : (False,                  "Defaults",  "bool", None),
    "owner"           : ("",                     "Defaults",  "str",  None),
    "permission"      : (644,                    "Defaults",  "int",  None),
    "prefix"          : ("",                     "Defaults",  "str",  None),
    "replace"         : ("",                     "Defaults",  "str",  None),
    "replace_pattern" : ("",                     "Defaults",  "str",  None),
    "secure"          : (True,                   "Defaults",  "bool", None),
    "suffix"          : ("",                     "Defaults",  "str",  None),
    "tags"            : ([],                     "Defaults",  "list", None),
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
    return values[name][0]

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
    if args.save:
        _set("save", args.save)
    # Load configs
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
        # Skip all values don't belong to any section in the config file
        if props[1] is None:
            continue
        # Set getter for config depending on value type
        getter = config.get
        if props[2] == "int":
            getter = config.getint
        elif props[2] == "bool":
            getter = config.getboolean
        # Get value from config. Prefer values from special installed section
        section = "Installed." + get("save") + "." + props[1]
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

    # Write arguments
    for arg, value in vars(args).items():
        if value is None or arg in ["config", "save"]:
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
    installed_file = os.path.join(data_dir, installed_path_template) % get("save")
    installed_backup = installed_file + "." + get("backup_extension")
    _set("installed_file", installed_file)
    _set("installed_backup", installed_backup)
