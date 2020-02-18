"""This module handles writing and loading installed-files. """

###############################################################################
#
# Copyright 2020 Erik Schulz
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
import json
import re
from copy import deepcopy
from collections.abc import MutableMapping
from collections.abc import MutableSequence
from uberdot import constants as const
from uberdot.upgrades import *
from uberdot.errors import UnkownError
from uberdot.errors import PreconditionError
from uberdot.utils import expandvars
from uberdot.utils import find_files
from uberdot.utils import get_current_username
from uberdot.utils import get_user_environ_path
from uberdot.utils import log_debug
from uberdot.utils import log_warning
from uberdot.utils import log
from uberdot.utils import makedirs
from uberdot.utils import safe_walk
from uberdot.utils import normpath
from uberdot.utils import create_symlink
from uberdot.utils import get_timestamp_now


PATH_VALUES = ["from", "to"]

class AutoExpander:
    def getitem(self, key):
        value = self.data[key]
        if isinstance(value, str):
            if key in PATH_VALUES:
                value = normpath(value)
            else:
                value = expandvars(value)
        return value

    def notify(self):
        pass

    def notify_change(self, handler):
        self.notify = handler

    def len(self):
        return len(self.data)

    def delitem(self, key):
        del self.data[key]

    def wrap_value(self, value):
        if isinstance(value, AutoExpander):
            return value
        val = value
        if type(value) == dict:
            val = AutoExpandDict(value)
            val.notify_change(self.notify)
        elif type(value) == list:
            val = AutoExpandList(value)
            val.notify_change(self.notify)
        return val


class AutoExpandDict(MutableMapping, AutoExpander):
    def __init__(self, args={}, **kwargs):
        self.data = {}
        self.update(args, **kwargs)

    def __getitem__(self, key): return self.getitem(key)
    def __delitem__(self, key): self.delitem(key)
    def __len__(self): return self.len()

    def __iter__(self):
        return iter(self.data)

    def __setitem__(self, key, value):
        self.data[key] = self.wrap_value(value)
        self.notify()

    def __repr__(self):
        rep = "{"
        for key in list(self.data.keys())[:-1]:
            rep += repr(key) + ": " + repr(self[key]) + ", "
        if self.len():
            last_key = list(self.data.keys())[-1]
            rep += repr(last_key) + ": " + repr(self[last_key])
        rep += "}"
        return rep


class AutoExpandList(MutableSequence, AutoExpander):
    def __init__(self, args=[]):
        self.data = []
        self.extend(args)

    def __getitem__(self, key): return self.getitem(key)
    def __delitem__(self, key): self.delitem(key)
    def __len__(self): return self.len()

    def __setitem__(self, value):
        self.data.append(self.wrap_value(value))
        self.notify()

    def insert(self, index, value):
        self.data.insert(index, self.wrap_value(value))
        self.notify()

    def __repr__(self):
        rep = "["
        for item in self[:-1]:
            rep += repr(item) + ", "
        if self.len():
            rep += repr(self[-1])
        rep += "]"
        return rep


class AutoExpanderJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AutoExpandDict):
            return dict(obj.items())
        if isinstance(obj, AutoExpandList):
            return list(obj)
        return super().default(obj)


class InstalledFile(MutableMapping):
    def __init__(self, timestamp=None):
        # Setup in-mememory installed file
        self.loaded = AutoExpandDict()
        self.loaded["@version"] = const.version
        # Load installed files of other users
        other_users = ["root"] + os.listdir("/home")
        other_users.remove(get_current_username())
        for user in other_users:
            path = get_user_environ_path(user)
            path = os.path.join(path, const.state_name)
            if not os.path.exists(path):
                # Ignore this user, if he has no installed file
                continue
            # Load file
            dict_ = json.load(open(path))
            # If we can't upgrade, ignore this installed file
            if is_version_smaller(dict_["@version"], MIN_VERSION):
                msg = "Ignoring installed file of user " + user + ". Too old."
                log_warning(msg)
                continue
            if is_version_smaller(const.version, dict_["@version"]):
                msg = "Ignoring installed file of user " + user + "."
                msg += " uberdot is too old."
                log_warning(msg)
                continue
            # Upgrade and store in loaded
            dict_ = self.upgrade(dict_)
            self.loaded[user] = dict_
        # Load installed files of current users
        self.own_file = os.path.join(const.environ_dir, const.state_name)
        path = self.own_file
        if timestamp is not None:
            path, ext = os.path.splitext(self.own_file)
            path += "_" + timestamp + "." + ext
        # Load file
        self.user_dict = AutoExpandDict()
        try:
            self.user_dict.update(json.load(open(path)))
        except FileNotFoundError:
            log_debug("No installed file found. Creating new.")
            self.user_dict = self.init_empty_installed()
        # Make sure to write file on changes in user_dict
        self.user_dict.notify_change(self.__write_file__)
        # Check if we can upgrade
        if is_version_smaller(self.user_dict["@version"], MIN_VERSION):
            msg = "Your installed file is too old to be processed."
            raise PreconditionError(msg)
        if is_version_smaller(const.version, self.user_dict["@version"]):
            msg = "Your installed file was created with a newer version of "
            msg += "uberdot. Please update uberdot before you continue."
            raise PreconditionError(msg)
        # Upgrade and store in loaded
        self.user_dict = self.upgrade(self.user_dict, True)
        self.loaded[get_current_username()] = self.user_dict
        # Make sure to update version in case no upgrade was needed
        self.user_dict["@version"] = const.version

    def init_empty_installed(self):
        empty = AutoExpandDict()
        empty["@version"] = const.version
        return empty

    def upgrade(self, installed_file, write=False):
        patches = []
        # Skip all upgrades for smaller versions
        for i, upgrade in enumerate(upgrades):
            if is_version_smaller(installed_file["@version"], upgrade[0]):
                patches = upgrades[i:]
                break
        # Apply patches in order
        for patch in patches:
            installed_file = patch[1](installed_file)
            installed_file["@version"] = patch[0]
            if write:
                self.__write_file__()
        return installed_file

    def create_snapshot(self):
        path, ext = os.path.splitext(self.own_file)
        path += "_" + get_timestamp_now() + "." + ext
        self.__write_file__(path)

    def __write_file__(self, path=None):
        if path is None:
            path = self.own_file
        makedirs(os.path.dirname(path))
        # Write content of self.loaded to file
        try:
            file = open(path, "w")
            file.write(json.dumps(
                self.user_dict,
                cls=AutoExpanderJSONEncoder,
                indent=4
            ))
        except OSError as err:
            msg = "An unkown error occured when trying to "
            msg += "write changes back to the installed-file."
            raise UnkownError(err, msg)
        finally:
            file.close()

    def get_special(self, key):
        return self.loaded["@" + key]

    def get_users(self):
        return [item for item in self.loaded if item[0] != "@"]

    def get_user_profiles(self, user):
        return self.loaded[user]

    def get_profiles(self):
        profiles = []
        for usr in self.get_users():
            for profile in self.loaded[usr]:
                if profile[0] != "@":
                    profiles.append((usr, self.loaded[usr][profile]))
        return profiles

    def __setitem__(self, key, value):
        self.user_dict[key] = value
        self.__write_file__()

    def __delitem__(self, key):
        del self.user_dict[key]
        self.__write_file__()

    def __getitem__(self, key):
        return self.user_dict[key]

    def copy(self):
        return deepcopy(self)

    def __len__(self):
        return len(self.user_dict)

    def __repr__(self):
        return repr(self.user_dict)

    def __iter__(self):
        return iter(self.user_dict)
