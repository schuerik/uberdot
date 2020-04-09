"""This module handles writing and loading state-files. """

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
from uberdot.utils import *

const = Const()


def build_statefile_path(timestamp=None):
    path = os.path.join(const.session_dir, const.STATE_NAME)
    if timestamp is not None:  # Load a previous snapshot
        path, ext = os.path.splitext(path)
        path += "_" + timestamp + ext
    return path

def get_timestamp_from_path(path):
    return int(path.split("_")[1][:-5])


###############################################################################
# Upgrades
###############################################################################

def is_version_smaller(version_a, version_b):
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


def upgrade_stone_age(old_state):
    """Upgrade from old installed file with schema version 4 to fancy
    state file. Luckily the schema only introduced optional properties
    and renamed "name" to "from" and "target" to "to".
    """
    for key in old_state:
        for link in old_state[key]["links"]:
            # Rename name and target
            link["from"] = link["name"]
            del link["name"]
            link["to"] = link["target"]
            del link["target"]
            # Convert gid and uid to owner string
            gid = link["gid"]
            try:
                username = get_username(link["uid"])
            except KeyError:
                username = ""
            try:
                groupname = get_groupname(link["gid"])
            except KeyError:
                groupname = ""
            link["owner"] = username + ":" + groupname
            del link["uid"]
            del link["gid"]
    return old_state

def upgrade_flexible_events(old_state):
    """Upgrade event properties. Instead of a simple boolean it contains
    the scripts md5-hash as reference and is now mandantory.
    """
    for key in old_state:
        events = ["beforeInstall", "afterInstall", "beforeUpdate",
                  "afterUpdate", "beforeUninstall", "afterUninstall"]
        for event in events:
            if event not in old_state[key]:
                old_state[key][event] = ""
            else:
                # TODO test this upgrade
                script_dir = os.path.join(const.session_dir, "scripts") + "/"
                script_link = script_dir + key + "_" + event
                if os.path.exists(script_link):
                    script_path = readlink(script_link)
                    old_state[key][event] = script_path[-35:-3]
                else:
                    old_state[key][event] = ""
    return old_state

MIN_VERSION = "1.12.17_4"
upgrades = [
    ("1.17.0", upgrade_stone_age),
    ("1.18.0", upgrade_flexible_events),
]



###############################################################################
# Helper classes to interact with state file
###############################################################################

PATH_VALUES = ["from", "to"]

class Notifier:
    def __init__(self):
        # Activte notify on end of init. That way subclasses can initialize
        # themself without triggering notify
        self.notify = self._notify

    def set_parent(self, parent):
        if parent is not None and not isinstance(parent, Notifier):
            raise FatalError(str(parent) + " needs to be Notifier")
        self.parent = parent

    def notify(self):
        pass

    def _notify(self):
        if hasattr(self, "parent") and self.parent is not None:
            if hasattr(self.parent, "notify") and self.parent.notify is not None:
                self.parent.notify()

    def copy(self):
        clone = deepcopy(self)
        clone.parent = None
        return clone


class AutoExpander(Notifier):
    def getitem(self, key):
        value = self.data[key]
        # Expand values
        if isinstance(value, str):
            # Normalize path
            if key in PATH_VALUES:
                value = normpath(value)
            # Inflate owner
            elif key == "owner":
                value = inflate_owner(value)
            # Expand environment vars
            else:
                value = expandvars(value)
        return value

    def len(self):
        return len(self.data)

    def delitem(self, key):
        del self.data[key]
        self.notify()

    def wrap_value(self, value):
        # Wrap dicts and lists into AutoExpanders
        if type(value) == dict:
            value = AutoExpandDict(value)
        elif type(value) == list:
            value = AutoExpandList(value)
        # If we got a Notifier or just wraped a dict or a list,
        # we set this instance as its parent
        if isinstance(value, Notifier):
            value.set_parent(self)
        return value

class AutoExpandDict(MutableMapping, AutoExpander):
    def __init__(self, args={}, **kwargs):
        # Init fields and load data
        self.data = {}
        self.data_specials = {}
        self.update(args, **kwargs)
        super().__init__()

    def __getitem__(self, key): return self.getitem(key)
    def __delitem__(self, key): self.delitem(key)
    def __len__(self): return self.len()

    def __iter__(self):
        return iter(self.data)

    def __setitem__(self, key, value):
        if key[0] == "@":
            self.set_special(key[1:], value)
        else:
            self.data[key] = self.wrap_value(value)
            self.notify()

    def get_specials(self):
        return self.data_specials

    def get_special(self, key, default=None):
        if default is not None and not key in self.data_specials:
            return default
        return self.data_specials[key]

    def set_special(self, key, value):
        self.data_specials[key] = value
        self.notify()

    def __repr__(self):
        def dict_repr(dict_, prefix=""):
            return ", ".join(
                [prefix + repr(key) + ": " + repr(dict_[key]) for key in dict_]
            )
        data_result = dict_repr(self)
        special_result = dict_repr(self.data_specials, "@")
        result = "AutoExpandDict{" + special_result
        if special_result and data_result:
            result += ", "
        result += data_result
        result += "}"
        return result


class AutoExpandList(MutableSequence, AutoExpander):
    def __init__(self, args=[], parent=None):
        # Init fields and load data
        self.data = []
        self.extend(args)
        super().__init__()

    def __getitem__(self, index): return self.getitem(index)
    def __delitem__(self, index): self.delitem(index)
    def __len__(self): return self.len()

    def __setitem__(self, value):
        self.data.append(self.wrap_value(value))
        self.notify()

    def insert(self, index, value):
        self.data.insert(index, self.wrap_value(value))
        self.notify()

    def __repr__(self):
        rep = "AutoExpandList["
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


###############################################################################
# Main classes
###############################################################################

class GlobalState(metaclass=Singleton):
    def load(self):
        # Load current state file of current user
        self.states = {}
        self.states[const.user] = State.current()
        # Load current state files of other users
        for user, session_path in const.session_dirs_foreign:
            self.try_load_user_session(user, session_path)

    def try_load_user_session(self, user, session_dir):
        path = os.path.join(session_dir, const.STATE_NAME)
        # Ignore this user, if he has no state file
        if not os.path.exists(path):
            return
        # Load file
        state = State.fromFile(path, auto_upgrade=False)
        # If we can't upgrade, ignore this state file
        if is_version_smaller(state.get_special("version"), MIN_VERSION):
            msg = "Ignoring state file of user " + user + ". Too old."
            log_warning(msg)
            return
        if is_version_smaller(const.VERSION, state.get_special("version")):
            msg = "Ignoring state file of user " + user + "."
            msg += " uberdot is too old."
            log_warning(msg)
            return
        # Upgrade and store in loaded
        try:
            state.full_upgrade()
            self.states[user] = state
        except CustomError as err:
            msg = "An error occured when upgrading the state file of user "
            msg += user + ". Ignoring."
            log_warning(msg)
            # We shouldn't ignore it if we are testing at the moment
            if const.test:
                raise err

    def get_users(self):
        return self.states.keys()

    def get_user_state(self, user):
        return self.states[user]

    def get_profiles(self):
        profiles = []
        for usr in self.get_users():
            for profile in self.states[usr]:
                profiles.append((usr, self.states[usr][profile]))
        return profiles

    @property
    def current(self):
        return self.states[const.user]


# TODO verify that the state gets the correct snapshot property and
# behaves consistent with auto_write
class State(AutoExpandDict):
    def __init__(self, file, auto_write=False, auto_upgrade=True):
        # Setup in-mememory state file
        self.file = file
        # Load state files of current user
        log_debug("Loading state file '" + self.file + "'.")
        try:
            super().__init__(json.load(open(self.file)))
        except json.decoder.JSONDecodeError as err:
            raise PreconditionError(
                "Can not parse '" + self.file + "'. " + str(err)
            )
        except FileNotFoundError:
            raise PreconditionError(
                "State file '" + self.file + "' doesn't exist."
            )
        # Setup auto write
        self.auto_write = auto_write
        # Upgrade
        if auto_upgrade:
            self.full_upgrade()

    @classmethod
    def fromTimestamp(cls, timestamp):
        return cls(build_statefile_path(timestamp))

    @staticmethod
    def fromTimestampBefore(timestamp):
        for n, file in enumerate(State._get_snapshots(const.session_dir)):
            if get_timestamp_from_path(file) > timestamp:
                break
        return State.fromIndex(n-1)

    @classmethod
    def fromFile(cls, file, auto_upgrade):
        return cls(file, auto_upgrade=auto_upgrade)

    @staticmethod
    def fromNumber(number):
        return State.fromIndex(number-1)

    @staticmethod
    def fromIndex(index):
        file = State._get_snapshots(const.session_dir)[index]
        return State.fromFile(file)

    @classmethod
    def current(cls):
        path = build_statefile_path()
        if not os.path.exists(path):
            log_debug("No state file found. Creating new.")
            makedirs(os.path.dirname(path))
            file = open(path, "w")
            file.write('{"@version": "' + const.VERSION + '"}')
            file.close()
        return cls(path, auto_write=True)

    @staticmethod
    def _get_snapshots(state_dir):
        snapshots = []
        for file in listfiles(state_dir):
            if re.fullmatch(r".*/state_\d{10}\.json", file):
                snapshots.append(file)
        return sorted(snapshots)

    def get_snapshots(self):
        return State._get_snapshots(os.path.dirname(self.file))

    def upgrade(self, patch):
        try:
            self.loaded = patch[1](self.loaded)
            self.loaded.set_special("version", patch[0])
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured when trying to upgrade the "
            msg += "state. Please resolve this error first."
            raise UnkownError(err, msg)

    def full_upgrade(self):
        # Check if we can upgrade
        if is_version_smaller(self.get_special("version"), MIN_VERSION):
            msg = "Your state file is too old to be processed."
            raise PreconditionError(msg)
        if is_version_smaller(const.VERSION, self.get_special("version")):
            msg = "Your state file was created with a newer version of "
            msg += "uberdot. Please update uberdot before you continue."
            raise PreconditionError(msg)
        # Turn of auto_write temporarily
        auto_write = self.auto_write
        self.auto_write = False
        # Upgrade and store in loaded
        patches = self.get_patches()
        if auto_write:
            for patch in patches:
                log(
                    "Upgrading state file to version " + patch[0] + " ... ",
                    end=""
                )
                self.upgrade(patch)
                self.write_file()
                log("Done.")
        else:
            log_debug(
                "Upgrading state file to version " + patches[-1][0]  + " ... ",
                end=""
            )
            for patch in patches:
                self.upgrade(patch)
            log_debug("Done.")
        if not patches:
            # Make sure to update version in case no upgrade was performed
            self.set_special("version", const.VERSION)
        # Restore auto_write
        self.auto_write = auto_write

    def get_patches(self):
        patches = []
        # Skip all upgrades for smaller versions
        for i, upgrade in enumerate(upgrades):
            if is_version_smaller(self.get_special("version"), upgrade[0]):
                patches = upgrades[i:]
                break
        return patches

    def create_snapshot(self):
        path, ext = os.path.splitext(self.file)
        timestamp = get_timestamp_now()
        path += "_" + timestamp + ext
        log_debug("Creating state file snapshot at '" + path + "'.")
        self.set_special("snapshot", timestamp)
        self.write_file(path)
        return timestamp

    def write_file(self, path=None):
        # Prepare directory
        if path is None:
            path = self.file
        makedirs(os.path.dirname(path))
        # Merge user_dict with specials
        new_dict = {}
        new_dict.update(self)
        new_dict.update(
            map(
                # Prepend the removed @ signs to special values
                lambda x: ("@"+x[0], x[1]),
                self.get_specials().items()
            )
        )
        # Write content to file
        try:
            file = open(path, "w")
            file.write(
                json.dumps(new_dict, cls=AutoExpanderJSONEncoder, indent=4)
            )
        except OSError as err:
            msg = "An unkown error occured when trying to "
            msg += "write changes back to the state file."
            raise UnkownError(err, msg)
        finally:
            file.close()

    def _notify(self):
        if self.auto_write:
            log_debug("Writing changes back to state file.")
            self.write_file()

    def copy(self):
        clone = super().copy()
        clone.auto_write = False
        return clone
