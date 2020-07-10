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


def upgrade_stone_age(old_state, path):
    """Upgrade from old installed file with schema version 4 to fancy
    state file.
    """
    for key in old_state:
        if key.startswith("@"):
            continue
        for link in old_state[key]["links"]:
            # Rename name
            link["path"] = link["name"]
            del link["name"]
            # Add target inode
            abstarget = os.path.join(os.path.dirname(path), link["target"])
            link["target_inode"] = None
            if os.path.exists(abstarget):
                link["target_inode"] = os.stat(link["target"]).st_ino
            # Convert gid and uid to owner string
            gid = link["gid"]
            try:
                username = get_username(link["uid"])
            except KeyError:
                msg = "No user with id " + link["uid"] + " found."
                msg += "Using the current user as fallback."
                log_debug(msg)
                username = ""
            try:
                groupname = get_groupname(link["gid"])
            except KeyError:
                msg = "No group with id " + link["gid"] + " found."
                msg += "Using the current group as fallback."
                log_debug(msg)
                groupname = ""
            link["owner"] = username + ":" + groupname
            del link["uid"]
            del link["gid"]
            # Add hard property
            link["hard"] = False
    return old_state

def upgrade_flexible_events(old_state, path):
    """Upgrade event properties. Instead of a simple boolean it contains
    the scripts md5-hash as reference and is now mandantory.
    """
    for key in old_state:
        if key.startswith("@"):
            continue
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
    # TODO upgrade for hardlinks needed
]



###############################################################################
# Helper classes to interact with state file
###############################################################################

class Notifier:
    def __init__(self):
        self.init_data()
        # Activte notify on end of init. That way subclasses can initialize
        # themself without triggering notify
        self.notify = self.__notify

    def set_parent(self, parent):
        if parent is not None and not isinstance(parent, Notifier):
            raise FatalError(str(parent) + " needs to be Notifier")
        self.parent = parent

    def notify(self):
        pass

    def __notify(self):
        if hasattr(self, "parent") and self.parent is not None:
            if hasattr(self.parent, "notify") and self.parent.notify is not None:
                self.parent.notify()

    def copy(self):
        clone = deepcopy(self)
        clone.parent = None
        return clone

    def init_data(self):
        pass


class AutoExpander(Notifier):
    def __init__(self, origin):
        self.origin = origin
        self.expander = {}
        super().__init__()

    def getitem(self, key):
        return self.expandvalue(key, self.data[key])

    def len(self):
        return len(self.data)

    def delitem(self, key):
        del self.data[key]
        self.notify()

    def expandvalue(self, key, value):
        if key in self.expander:
            if value is not None:
                value = self.expander[key](value)
        return value

    def wrap_value(self, key, value):
        # If we got a Notifier or just wraped a dict or a list,
        # we set this instance as its parent
        if isinstance(value, Notifier):
            value.set_parent(self)
        return value


class AutoExpandDict(MutableMapping, AutoExpander):
    def __init__(self, origin, args={}, **kwargs):
        # Init fields and load data
        self.data = {}
        self.data_specials = {}
        super().__init__(origin)
        self.update(args, **kwargs)

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
    def __init__(self, origin, args=[]):
        # Init fields and load data
        self.data = []
        super().__init__(origin)
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
            raise PreconditionError("Cannot create new key '" + key + "' in a StaticAutoExpandDict")


class LinkData(StaticAutoExpandDict):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args, **kwargs)
        # TODO normpath needs to normalize relative to origin here
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
            target = readlink(path)
            props["target"] = target
            props["target_inode"] = os.stat(target).st_ino
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
            value = BuildupData(self.origin, value)
        return super().wrap_value(key, value)


class BuildupData(AutoExpandDict):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args, **kwargs)
        self.expander["path"] = normpath

    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None

    def wrap_value(self, key, value):
        if key == "source":
            if type(value) == dict and "type" in value:
                if value["type"] == "StaticFile":
                    value = CopyData(self.origin, value)
                else:
                    value = BuildupData(self.origin, value)
            else:
                raise ValueError("UnsupportedType")
        return super().wrap_value(key, value)


class CopyData(AutoExpandDict):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args, **kwargs)
        self.expander["path"] = normpath
        self.expander["source"] = normpath

    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None


class ProfileStateDict(AutoExpandDict):
    def wrap_value(self, key, value):
        if key == "links" and not isinstance(value, LinkContainerList):
            value = LinkContainerList(self.origin, value)
        return super().wrap_value(key, value)


class LinkContainerList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = LinkData(self.origin, value)
        return super().wrap_value(key, value)


###############################################################################
# Main classes
###############################################################################

class GlobalState(metaclass=Singleton):
    def load(self):
        # Load current state file of current user
        self.states = {}
        self.states[const.internal.user] = OwnState.current()
        # Load current state files of other users
        for user, session_path in const.internal.session_dirs_foreign:
            self.try_load_user_session(user, session_path)

    def try_load_user_session(self, user, session_dir):
        path = os.path.join(session_dir, const.internal.STATE_NAME)
        # Ignore this user, if he has no state file
        if not os.path.exists(path):
            return
        # Load file
        try:
            state = ForeignState.fromFile(path)
            self.states[user] = state
        except CustomError as err:
            if isinstance(err, UnkownError):
                log_debug(err.original_message)
            else:
                log_debug(err._message)
            msg = "An error occured when upgrading the state file of user "
            msg += user + ". Ignoring this state file."
            log_warning(msg)
            # We shouldn't ignore it if we are testing at the moment
            if const.internal.test:
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
    def __init__(self, file, auto_write=False):
        # Setup in-mememory state file
        self.origin = file
        # Load state files of current user
        log_debug("Loading state file '" + self.origin + "'.")
        try:
            self.state_raw = json.load(open(self.origin))
        except json.decoder.JSONDecodeError as err:
            raise PreconditionError(
                "Can not parse '" + self.origin + "'. " + str(err)
            )
        except FileNotFoundError:
            raise PreconditionError(
                "State file '" + self.origin + "' doesn't exist."
            )
        # Setup auto write
        self.auto_write = auto_write
        # Upgrade
        self._upgrade()
        super().__init__(self.origin, self.state_raw)

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
    def fromFile(cls, file):
        return cls(file)

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
        return get_snapshots(os.path.dirname(self.origin))

    def get_patches(self):
        patches = []
        # Skip all upgrades for smaller versions
        for i, upgrade in enumerate(upgrades):
            if is_version_smaller(self.state_raw["@version"], upgrade[0]):
                patches = upgrades[i:]
                break
        return patches

    def __apply_patch(self, patch):
        try:
            self.state_raw = patch[1](deepcopy(self.state_raw), self.origin)
            self.state_raw["@version"] = patch[0]
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured when trying to upgrade the "
            msg += "state. Please resolve this error first."
            raise UnkownError(err, msg)

    def _upgrade(self, extended_logging=False):
        # Check version
        version = self.state_raw["@version"]
        if is_version_smaller(version, const.internal.MIN_VERSION):
            msg = "State file is too old to be processed."
            raise PreconditionError(msg)
        if is_version_smaller(const.internal.VERSION, version):
            msg = "State file was created with a newer version of "
            msg += "uberdot. Please update uberdot before you continue."
            raise PreconditionError(msg)
        # Get and apply patches to state_raw
        patches = self.get_patches()
        if not extended_logging and patches:
            log_debug(
                "Upgrading state file to version " + patches[-1][0]  + " ... ",
                end=""
            )
        for patch in patches:
            if extended_logging:
                log(
                    "Upgrading state file to version " + patch[0] + " ... ",
                    end=""
                )
            self.__apply_patch(patch)
            if extended_logging:
                log("Done.")
        if not extended_logging:
            log_debug("Done.")
        # Update version number
        self.state_raw["@version"] = const.internal.VERSION

    def create_snapshot(self):
        path, ext = os.path.splitext(self.origin)
        timestamp = get_timestamp_now()
        path += "_" + timestamp + ext
        log_debug("Creating state file snapshot at '" + path + "'.")
        self.set_special("snapshot", timestamp)
        self.write_file(path)
        return timestamp

    def write_file(self, path=None):
        # Prepare directory
        if path is None:
            path = self.origin
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


class OwnState(State):
    def __init__(self, path, auto_write=False):
        super().__init__(path, auto_write=auto_write)
        self.write_file()


class ForeignState(State):
    def __init__(self, path):
        super().__init__(path, auto_write=False)
