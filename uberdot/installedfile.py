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
from uberdot import constants as const
from uberdot.errors import UnkownError
from uberdot.errors import PreconditionError
from uberdot.utils import get_current_username
from uberdot.utils import log_debug
from uberdot.utils import log
from uberdot.utils import expandvars
from uberdot.utils import normpath
from uberdot.utils import create_symlink
from uberdot.utils import get_timestamp_now
from uberdot.utils import version_is_smaller


PATH_VALUES = ["from", "to"]
MIN_VERSION = "1.16.0"

class AutoExpandDict(dict):
    def __getitem__(self, key):
        if key in PATH_VALUES:
            value = normpath(self.__dict__[key])
        else:
            value = expandvars(self.__dict__[key])
        return value

class InstalledFile(dict):
    def upgrade_owner(self, old_loaded):
        return old_loaded

    upgrades = [
        ("1.17.0", upgrade_owner)
    ]
    def __init__(self, timestamp=None):
        # Load the file and setup fields
        if timestamp is None:
            path = const.installed_file
        else:
            path, ext = os.path.splitext(const.installed_file)
            path += timestamp + "." + ext
        self.loaded = AutoExpandDict()
        try:
            self.loaded.update(**json.load(open(path)))
            if self.is_version_smaller(MIN_VERSION):
                msg = "Installed file is too old to be processed."
                raise PreconditionError(msg)
            if self.is_version_smaller(self.loaded["@version"], const.version):
                msg = "Installed file was modified using version "
                msg += self.loaded["@version"] + " but is only at version "
                msg += const.version + ". Please update uberdot to proceed."
                raise PreconditionError(msg)
        except FileNotFoundError:
            log_debug("No installed file found.")
        self.loaded["@version"] = const.version
        usr = get_current_username()
        if usr not in self.loaded:
            self.loaded[usr] = {}
        self.user_dict = AutoExpandDict(self.loaded[usr])
        if timestamp is not None:
            # The most recent installed file was loaded so we write it
            # right now, in case something has been already changed and
            # to verify that we have write access to this file
            self.__write_file__()
            # Furthermore we need to make sure that it matches the filesystem
            self.fix()

    def is_version_smaller(self, version_b, version_a=self.loaded["@version"]):
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_a)
        major_a, minor_a, patch_a = match.groups()
        major_a, minor_a, patch_a = int(major_a), int(minor_a), int(patch_a)
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_b)
        major_b, minor_b, patch_b = match.groups()
        major_b, minor_b, patch_b = int(major_b), int(minor_b), int(patch_b)
        if major_a > major_b:
            return False
        if major_a < major_b:
            return True
        if minor_a > minor_b:
            return False
        if minor_a < minor_b:
            return True
        if patch_a > patch_b:
            return False
        if patch_a < patch_b:
            return True
        return False

    def upgrade(self):
        patches = []
        for i, upgrade in enumerate(self.upgrades):
            if self.is_version_smaller(upgrade[0]):
                patches = upgrades[i:]
                break
        for patch in patches:
            log("Upgrading installed file to version " + patch[0])
            self.loaded = patch[1](self.loaded)
            self.loaded["@version"] = patch[0]
            self.__write_file__()

    def create_snapshot(self):
        path, ext = os.path.splitext(const.installed_file)
        path += "_" + get_timestamp_now() + "." + ext
        self.__write_file__(path)

    def fix(self):
        def fix_link(self, fix_description, remove=None):
            selection = input(fix_description + " (s/r/F/?) ")
            if selection.lower() == "s":
                return
            elif selection == "F":
                del link
            elif selection == "r":
                if remove is not None:
                    os.remove(remove)
                create_symlink(**link)
            else:
                if selection == "?":
                    log("(s)kip / (r)estore link / (F)orget link")
                else:
                    log("Unkown option")
                fix_link(fix_description, remove)

        for key in self.keys():
            for link in self[key]["links"]:
                if not os.path.exists(link["name"]):
                    for root, _, name in os.walk(os.path.dirname(link["name"])):
                        file = os.path.join(root, name)
                        if os.path.realpath(file) == link["target"]:
                            msg = "Link '" + link["name"] + "' was renamed '"
                            msg += " to '" + file + "'."
                            fix_link(msg, file)
                            break
                    fix_link("Link '" + link["name"] + "' was removed.")
                elif os.path.realpath(link["name"]) != link["target"]:
                    msg = "Link '" + link["name"] + "' now points to '"
                    msg += link["target"] + "'."
                    fix_link(msg, link["name"])
                # TODO: Check for props
        self.__write_file__()

    def __write_file__(self, path=const.installed_file):
        try:
            file = open(path, "w")
            file.write(json.dumps(self.loaded, indent=4))
        except OSError as err:
            msg = "An unkown error occured when trying to "
            msg += "write changes back to the installed-file."
            raise UnkownError(err, msg)
        finally:
            file.close()
        os.chmod(path, 666)

    def get_special(self, key):
        return self.loaded["@" + key]

    def get_users(self):
        return [item for item in self.loaded.keys() if item[0] != "@"]

    def get_user_profiles(self, user):
        return self.loaded[user]

    def get_profiles(self):
        profiles = []
        for usr in self.get_users():
            for profile in self.loaded[usr].keys():
                profiles.append((usr, profile))
        return profiles

    def __setitem__(self, key, value):
        self.user_dict[key] = value
        self.__write_file__()

    def update(self, *args, **kwargs):
        return self.user_dict.update(*args, **kwargs)

    def __delitem__(self, key):
        del self.user_dict[key]
        self.__write_file__()

    def keys(self):
        return self.user_dict.keys()

    def has_key(self, key):
        return key in self.keys()

    def __getitem__(self, key):
        return self.user_dict[key]

    def copy(self):
        return deepcopy(self)

    def clear(self):
        self.user_dict.clear()
        self.__write_file__()

    def __len__(self):
        return len(self.user_dict)

    def __repr__(self):
        return repr(self.user_dict)

    def values(self):
        return self.user_dict.values()

    def items(self):
        return self.user_dict.items()

    def pop(self, *args):
        item = self.user_dict.pop(*args)
        self.__write_file__()
        return item

    def __cmp__(self, dict_):
        return self.user_dict.__cmp__(self.user_dict, dict_)

    def __contains__(self, item):
        return item in self.user_dict

    def __iter__(self):
        return iter(self.user_dict)

    def __unicode__(self):
        raise NotImplementedError
