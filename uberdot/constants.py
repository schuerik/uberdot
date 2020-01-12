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

# TODO: remove all old references on this module
# TODO: doc

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
            return cls._instances[cls]

class Const(metaclass=Singleton):
    def __init__(self, owd):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(sys.modules[__name__].__file__)),
            "data"
        )
        installed = os.path.join(data_dir, "installed/%s.json")
        searchpaths = [
            "/etc/uberdot",
            os.path.join(
                get_user_env_var('XDG_CONFIG_HOME', normpath('~/.config')),
                "uberdot"
            ),
            data_dir
        ]
        self.values = {
            # name: (value, was_overwritten, configsection, type, manipulation function)
            "cfg_files"       : ([],          False, None,        "list", None),
            "cfg_search_paths": (searchpaths, False, None,        "list", None),
            "col_bold"        : ('\033[1m',   False, None,        "str",  None),
            "col_endc"        : ('\033[0m',   False, None,        "str",  None),
            "col_fail"        : ('\033[91m',  False, None,        "str",  None),
            "col_nobold"      : ('\033[22m',  False, None,        "str",  None),
            "col_ok"          : ('\033[92m',  False, None,        "str",  None),
            "col_warning"     : ('\033[93m',  False, None,        "str",  None),
            "data_dir"        : (data_dir,    False, None,        "str",  None),
            "installed_file"  : (installed,   False, None,        "str",  None),
            "installed_backup": ("",          False, None,        "str",  None),
            "mode"            : ("",          False, None,        "str",  None),
            "owd"             : (owd,         False, None,        "str",  None),
            "version"         : ("1.12.17_4", False, None,        "str",  None),
            "dui"             : (False,       False, "Arguments", "bool", None),
            "force"           : (False,       False, "Arguments", "bool", None),
            "logfile"         : ("",          False, "Arguments", "path", None),
            "logginglevel"    : ("INFO",      False, "Arguments", "str",  str.upper),
            "makedirs"        : (False,       False, "Arguments", "bool", None),
            "profiles"        : ([],          False, "Arguments", "list", None),
            "save"            : ("default",   False, "Arguments", "str",  str.lower),
            "skiproot"        : (False,       False, "Arguments", "bool", None),
            "superforce"      : (False,       False, "Arguments", "bool", None),
            "askroot"         : (True,        False, "Settings",  "bool", None),
            "backup_extension": ("bak",       False, "Settings",  "str",  None),
            "color"           : (True,        False, "Settings",  "bool", None),
            "decrypt_pwd"     : (None,        False, "Settings",  "str",  None),
            "hash_separator"  : ("#",         False, "Settings",  "str",  None),
            "profile_files"   : ("",          False, "Settings",  "path", None),
            "tag_separator"   : ("%",         False, "Settings",  "str",  None),
            "target_files"    : ("",          False, "Settings",  "path", None),
            "directory"       : ("$HOME",     False, "Defaults",  "path", None),
            "extension"       : ("",          False, "Defaults",  "str",  None),
            "name"            : ("",          False, "Defaults",  "str",  None),
            "optional"        : (False,       False, "Defaults",  "bool", None),
            "owner"           : ("",          False, "Defaults",  "str",  None),
            "permission"      : (644,         False, "Defaults",  "int",  None),
            "prefix"          : ("",          False, "Defaults",  "str",  None),
            "replace"         : ("",          False, "Defaults",  "str",  None),
            "replace_pattern" : ("",          False, "Defaults",  "str",  None),
            "secure"          : (True,        False, "Defaults",  "bool", None),
            "suffix"          : ("",          False, "Defaults",  "str",  None),
            "tags"            : ([],          False, "Defaults",  "list", None),
        }
        self.defaults = dict(self.values)

    def reset(self):
        self.values = dict(self.defaults)

    def set(self, name, value):
        val_props = self.values[name]
        value = val_props[4](value)
        self.values[name] = value, True, val_props[2], val_props[3], val_props[4]

    def get(self, name):
        return self.values[name][0]

    def vals(self):
        return zip([item[2] for item in list(self.values.values())], list(self.values.keys()))

    def load(self, args):
        # Write arguments
        for arg, value in vars(args).items():
            name = arg
            # Parse tags and set values for --options
            if arg == "opt_dict":
                if "tags" in arg:
                    value["tags"] = next(csv.reader([value["tags"]]))
                for key, val in value.items():
                    self.set(key, val)
                continue
            # Relative paths need to be absolute
            if arg in ["directory", "config", "log"]:
                value = os.path.join(self.get(owd), value)
            # Little fixes for arguments where the names don't match up
            # with the configuration file argument
            if arg == "log":
                name = "logfile"
            elif arg in ["verbose", "info", "quiet", "silent"]:
                name = logginglevel
                value = arg
            elif arg == "config":
                name = "cfg_files"
                value = [value]
            # Set argument
            self.set(name, value)
        # Update internal values
        cfgs = find_files("uberdot.ini", self.get("cfg_search_paths"))
        cfgs += self.get("cfg_files")
        self.set("cfg_files", cfgs)
        # Load config
        config = configparser.ConfigParser()
        try:
            for cfg in cfgs:
                config.read(cfg)
                # We need to normalize all paths here, relatively to
                # the config file which it defined
                path_values = [
                    "directory", "profilefiles", "targetfiles",
                    "logfile"
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
        for name, props in self.values.items():
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
            section = "Installed." + self.get("save") + "." + props[2]
            if config.has_section(section) and config.has_option(section, name):
                value = getter(section, name)
            elif config.has_section(props[2]) and config.has_option(props[2], name):
                value = getter(section, props[2])
            else:
                # Value is not in config, skipping
                continue
            # Fix values depending on value type
            if props[3] == "list":
                value = next(csv.reader([value]))
            self.set(name, value)
        # Update internal values that depend on a loaded config
        installed_file = self.get("installed_file") % self.get("save")
        installed_backup = installed_file + "." + self.get("backup_extension")
        self.set("installed_file", installed_file)
        self.set("installed_backup", installed_backup)
        # Make values easy accessible
        for name, props in self.values.items():
            self.__dict__[name] = props[0]
