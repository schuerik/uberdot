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

upgrades = [
    ("1.17.0", upgrade_stone_age, None),
    ("1.18.0", upgrade_flexible_events, None),
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
    def __init__(self):
        self.expander = None
        self.init_data()

    def getitem(self, key):
        return self.expandvalue(key, self.data[key])

    def len(self):
        return len(self.data)

    def delitem(self, key):
        del self.data[key]
        self.notify()

    def expandvalue(self, key, value):
        return value

    def wrap_value(self, key, value):
        # If we got a Notifier or just wraped a dict or a list,
        # we set this instance as its parent
        if isinstance(value, Notifier):
            value.set_parent(self)
        return value

    def init_data(self):
        pass


class AutoExpandDict(MutableMapping, AutoExpander):
    def __init__(self, args={}, **kwargs):
        # Init fields and load data
        self.data = {}
        self.data_specials = {}
        super().__init__()
        self.expander = {}
        self.update(args, **kwargs)

    def expandvalue(self, key, value):
        if key in self.expander:
            value = self.expander[key](value)
        return value

    def __getitem__(self, key):
        if key[0] == "@":
            return self.get_special(key)
        return self.getitem(key)

    def __delitem__(self, key): self.delitem(key)
    def __len__(self): return self.len()
    def __iter__(self): return iter(self.data)

    def __setitem__(self, key, value):
        if key[0] == "@":
            self.set_special(key[1:], value)
        else:
            self.data[key] = self.wrap_value(key, value)
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
        result = type(self).__name__ + "{" + special_result
        if special_result and data_result:
            result += ", "
        result += data_result
        result += "}"
        return result


class AutoExpandList(MutableSequence, AutoExpander):
    def __init__(self, args=[]):
        # Init fields and load data
        self.data = []
        super().__init__()
        self.extend(args)

    def __getitem__(self, index): return self.getitem(index)
    def __delitem__(self, index): self.delitem(index)
    def __len__(self): return self.len()

    def __setitem__(self, value):
        self.data.append(self.wrap_value(self.len(), value))
        self.notify()

    def insert(self, index, value):
        self.data.insert(index, self.wrap_value(index, value))
        self.notify()

    def __repr__(self):
        rep = type(self).__name__ + "["
        for item in self[:-1]:
            rep += repr(item) + ", "
        if self.len():
            rep += repr(self[-1])
        rep += "]"
        return rep

    def expandvalue(self, key, value):
        if not isinstance(value, AutoExpander):
            value = self.expander(value)
        return value


class AutoExpanderJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AutoExpandDict):
            return dict(obj.items())
        if isinstance(obj, AutoExpandList):
            return list(obj)
        return super().default(obj)


class StaticAutoExpandDict(AutoExpandDict):
    def __setitem__(self, key, value):
        if key in self:
            super().__setitem__(key, value)
        else:
            raise FatalError("Cannot create new key '" + key + "' in a StaticAutoExpandDict")


class LinkData(StaticAutoExpandDict):
    def __init__(self, args={}, **kwargs):
        super().__init__(args, **kwargs)
        self.expander["path"] = normpath
        self.expander["target"] = normpath
        self.expander["owner"] = inflate_owner

    def init_data(self):
        # Path of the link itself
        self.data["path"] = None
        # Path of the file that the link points to
        self.data["target"] = None
        # Inode of the file that the link points to
        self.data["target_inode"] = None
        # Permission of the link itself
        self.data["permission"] = None
        # Owner of the link itself
        self.data["owner"] = None
        # Wether the owner of the link and the owner of the file
        # that link points to are the same
        self.data["secure"] = None
        # Wether this is a hard link
        self.data["hard"] = None
        # AbstractFile buildup data that can be used to trace back
        # how the content of the file that the link points to was generated
        self.data["buildup"] = None
        # Modification date of link itself
        self.data["updated"] = None
        # Creation date of link itself
        self.data["created"] = None

    @classmethod
    def from_file(cls, path):
        if not os.path.exists(path):
            raise FileNotFoundError
        props = {}
        props["path"] = path
        props["permission"] = get_permission(path)
        props["updated"] = timestamp_to_string(os.path.getmtime(path))
        props["created"] = timestamp_to_string(os.path.getctime(path))
        uid, gid = get_owner(path)
        props["owner"] = get_username(uid) + ":" + get_groupname(gid)
        props["hard"] = not os.path.islink(path)
        if props["hard"]:
            props["target_inode"] = os.stat(path).st_ino
        else:
            props["target"] = readlink(path)
            props["target_inode"] = os.stat(props["target"]).st_ino
            if os.path.exists(target):
                props["secure"] = get_owner(path) == get_owner(target)
        return cls(props)

    def broken(self):
        if self["hard"]:
            if self["target"] is not None:
                if os.stat(self["target"]).st_ino != self["target_inode"]:
                    return True
            if os.stat(self["path"]).st_ino != self["target_inode"]:
                return True
        else:
            if readlink(self["path"]) != self["target"]:
                return True
            if not os.path.exists(self["target"]):
                return True
        return False

    def exists(self):
        try:
            return self.is_same(LinkData.from_file(self["path"]))
        except FileNotFoundError:
            return False

    def similar_exists(self):
        try:
            if self.is_similar(LinkData.from_file(self["path"])):
                return True
        except FileNotFoundError:
            pass
        for file in listfiles(os.path.dirname(self["path"])):
            if self.is_similar(LinkData.from_file(file)):
                return True
        return False

    def is_similar(self, link):
        if self["path"] == link["path"]:
            return True
        if self["target"] is not None and link["target"] is not None:
            if self["target"] == link["target"]:
                return True
        return self["target_inode"] == link["target_inode"]

    def __eq__(self, link):
        result = self["path"] == link["path"]
        if self["target"] is not None and link["target"] is not None:
            result = result and self["target"] == link["target"]
        else:
            result = result and self["target_inode"] == link["target_inode"]
        result = result and self["owner"] == link["owner"]
        result = result and self["permission"] == link["permission"]
        result = result and self["hard"] == link["hard"]
        result = result and self["secure"] == link["secure"]
        return result

    def wrap_value(self, key, value):
        if key == "buildúp" and not isinstance(value, BuildupData):
            value = BuildupData(value)
        return super().wrap_value(key, value)


class BuildupData(AutoExpandDict):
    def __init__(self, args={}, **kwargs):
        super().__init__(args, **kwargs)
        self.expander["path"] = normpath

    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None

    def wrap_value(self, key, value):
        if key == "source":
            if type(value) == dict and "type" in value:
                if value["type"] == "StaticFile":
                    value = CopyData(value)
                else:
                    value = BuildupData(value)
            else:
                raise ValueError("UnsupportedType")
        return super().wrap_value(key, value)


class CopyData(AutoExpandDict):
    def __init__(self, args={}, **kwargs):
        super().__init__(args, **kwargs)
        self.expander["path"] = normpath
        self.expander["source"] = normpath

    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None


class ProfileStateDict(AutoExpandDict):
    def wrap_value(self, key, value):
        if key == "links" and not isinstance(value, LinkContainerList):
            value = LinkContainerList(value)
        return super().wrap_value(key, value)


class LinkContainerList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = LinkData(value)
        return super().wrap_value(key, value)


###############################################################################
# Main classes
###############################################################################

class GlobalState(metaclass=Singleton):
    def load(self):
        # Load current state file of current user
        self.states = {}
        self.states[const.internal.user] = State.current()
        # Load current state files of other users
        for user, session_path in const.internal.session_dirs_foreign:
            self.try_load_user_session(user, session_path)

    def try_load_user_session(self, user, session_dir):
        path = os.path.join(session_dir, const.internal.STATE_NAME)
        # Ignore this user, if he has no state file
        if not os.path.exists(path):
            return
        # Load file
        state = State.fromFile(path, auto_upgrade=False)
        # If we can't upgrade, ignore this state file
        if is_version_smaller(state.get_special("version"), const.internal.MIN_VERSION):
            msg = "Ignoring state file of user " + user + ". Too old."
            log_warning(msg)
            return
        if is_version_smaller(const.internal.VERSION, state.get_special("version")):
            msg = "Ignoring state file of user " + user + "."
            msg += " uberdot is too old."
            log_warning(msg)
            return
        # Upgrade and store in loaded
        try:
            state.full_upgrade()
            self.states[user] = state
        except CustomError as err:
            log_debug(str(err))
            msg = "An error occured when upgrading the state file of user "
            msg += user + ". Ignoring this state file."
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
        return self.states[const.internal.user]


# TODO verify that the state gets the correct snapshot property and
# behaves consistent with auto_write
class State(AutoExpandDict):
    def __init__(self, file, auto_write=False, auto_upgrade=True):
        # Setup in-mememory state file
        self.file = file
        # Load state files of current user
        log_debug("Loading state file '" + self.file + "'.")
        try:
            # TODO state needs to be upgraded before it is loaded into this class
            state_raw = json.load(open(self.file))
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
        super().__init__()

    @classmethod
    def fromTimestamp(cls, timestamp):
        return cls(build_statefile_path(timestamp))

    @staticmethod
    def fromTimestampBefore(timestamp):
        for n, file in enumerate(State._get_snapshots(const.session_dir)):
            if int(get_timestamp_from_path(file)) > int(timestamp):
                break
        return State.fromIndex(n-1)

    @classmethod
    def fromFile(cls, file, auto_upgrade=True):
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
            file.write('{"@version": "' + const.internal.VERSION + '"}')
            file.close()
        return cls(path, auto_write=True)

    def get_snapshots(self):
        return get_snapshots(os.path.dirname(self.file))

    def get_upgraded(self, patch):
        try:
            result = patch[1](deepcopy(self.data))
            result["@version"] = patch[0]
            return result
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured when trying to upgrade the "
            msg += "state. Please resolve this error first."
            raise UnkownError(err, msg)

    def full_upgrade(self):
        # Check if we can upgrade
        if is_version_smaller(self.get_special("version"), const.internal.MIN_VERSION):
            msg = "Your state file is too old to be processed."
            raise PreconditionError(msg)
        if is_version_smaller(const.internal.VERSION, self.get_special("version")):
            msg = "Your state file was created with a newer version of "
            msg += "uberdot. Please update uberdot before you continue."
            raise PreconditionError(msg)
        # Turn of auto_write temporarily, so that we don't write the file
        # for any minor change but only for each applied patch
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
                self.update(self.get_upgraded(patch))
                self.write_file()
                log("Done.")
                if patch[2]:
                    log_warning(
                        "Manual changes to your profiles might be required " +
                        "due to this upgrade: " + patch[2]
                    )
        elif patches:
            log_debug(
                "Upgrading state file to version " + patches[-1][0]  + " ... ",
                end=""
            )
            for patch in patches:
                self.update(self.get_upgraded(patch))
            log_debug("Done.")
        if not patches:
            # Make sure to update version in case no upgrade was performed
            self.set_special("version", const.internal.VERSION)
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

    def wrap_value(self, key, value):
        if type(value) == dict:
            value = ProfileStateDict(value)
        return super().wrap_value(key, value)

    def _notify(self):
        if self.auto_write:
            log_debug("Writing changes back to state file.")
            self.write_file()

    def copy(self):
        clone = super().copy()
        clone.auto_write = False
        return clone
