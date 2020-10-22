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
from uberdot import utils

FatalError = utils.FatalError
PreconditionError = utils.PreconditionError
CustomError = utils.CustomError
UnkownError = utils.UnkownError
UberdotError = utils.UberdotError
log = utils.log
log_debug = utils.log_debug
log_warning = utils.log_warning

const = utils.Const()


###############################################################################
# Upgrades
###############################################################################

def is_version_smaller(version_a, version_b):
    match = re.search(r"^(\d+)\.(\d+)\.(\d+)", version_a)
    major_a, minor_a, patch_a = match.groups()
    major_a, minor_a, patch_a = int(major_a), int(minor_a), int(patch_a)
    match = re.search(r"^(\d+)\.(\d+)\.(\d+)", version_b)
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


def upgrade_owner(old_state, path):
    for key in old_state:
        if key.startswith("@"):
            continue
        for link in old_state[key]["links"]:
            # Convert gid and uid to owner string
            gid = link["gid"]
            try:
                username = utils.get_username(link["uid"])
            except KeyError:
                msg = "No user with id " + link["uid"] + " found."
                msg += "Using the current user as fallback."
                raise PreconditionError(msg)
            try:
                groupname = utils.get_groupname(link["gid"])
            except KeyError:
                msg = "No group with id " + link["gid"] + " found."
                msg += "Using the current group as fallback."
                raise PreconditionError(msg)
            link["owner"] = username + ":" + groupname
            del link["uid"]
            del link["gid"]
    return old_state


def upgrade_owner_manual(olds_state, path):
    msg = "We can't upgrade your state file at '" + path + "' automatically."
    msg += "To upgrade this file yourself, edit the file and replace all 'uid'"
    msg += " and 'guid' properties with the new 'owner' property. 'uid' and 'guid'"
    msg += " were used to store the owner of each link. The new property will accept"
    msg += " a string in the format 'username:groupname'."
    return msg


def upgrade_date(old_state, path):
    for key in old_state:
        if key.startswith("@"):
            continue
        for link in old_state[key]["links"]:
            # Add created and modified date property and remove the old one
            link["created"] = link["date"]
            link["modified"] = link["date"]
            del link["date"]
    return old_state


# use this new version as "base" version, so all tests use at least this version
def upgrade_hard_links(old_state, path):
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
            abstarget = utils.abspath(link["target"], origin=path)
            link["target_inode"] = None
            if os.path.exists(abstarget):
                link["target_inode"] = os.stat(abstarget).st_ino
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
        # Upgrade event properties
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

# (version, function for automatic upgrade, function for manual update)
# How it works:
# (version, func1, None) -> func1 will be executed. if func1 fails the update failes
# (version, None, func2) -> func2 will be executed and shows instructions for user
# (version, func1, func2) -> only if func1 fails, func2 will show further instructions
# (version, None, None) -> No information on how to update available
# The list needs to be sorted by version numbers
upgrades = [
    ("1.13.2_4", None, None),
    ("1.14.0", upgrade_owner, upgrade_owner_manual),
    ("1.15.0", upgrade_date, None),
    ("1.17.0", upgrade_hard_links, None),
    ("1.18.0", upgrade_flexible_events, None),
]



###############################################################################
# Helper classes to interact with state file
###############################################################################

class Notifier:
    def __init__(self):
        self.notify_active = True
        self.notify = self._notify

    def set_parent(self, parent):
        if parent is not None and not isinstance(parent, Notifier):
            raise FatalError(str(parent) + " needs to be Notifier")
        self.parent = parent

    def notify(self):
        pass

    def _notify(self):
        if not hasattr(self, "parent") or self.parent is None:
            return
        if not hasattr(self.parent, "notify") or self.parent.notify is None:
            return
        if self.notify_active:
            self.parent.notify()

    def copy(self):
        clone = deepcopy(self)
        clone.parent = None
        return clone


class AutoExpander(Notifier):
    def __init__(self, origin=None):
        if origin is not None and not isinstance(origin, str):
            raise TypeError("origin needs to be of type string, not " + type(origin).__name__)
        self.origin = origin
        self.expander = {}
        self.init_data()
        # Activte notifier after init_data. That way subclasses can initialize
        # themself without triggering notify
        super().__init__()

    def init_data(self):
        pass

    @staticmethod
    def abspath(origin):
        def modded_abspath(path):
            return utils.abspath(path, origin=origin)
        return modded_abspath

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
    def __init__(self, origin=None, args={}, **kwargs):
        # Init fields and load data
        self.data = {}
        self.data_specials = {}
        super().__init__(origin)
        self.update(args, **kwargs)

    def update(self, args, **kwargs):
        self.notify_active = False
        super().update(args, **kwargs)
        self.notify_active = True
        self.notify()

    def __getitem__(self, key):
        if key is None:
            raise TypeError("key must not be None.")
        if key[0] == "@":
            return self.get_special(key)
        return self.getitem(key)

    def __delitem__(self, key): self.delitem(key)
    def __len__(self): return self.len()
    def __iter__(self): return iter(self.data)

    def __setitem__(self, key, value):
        if key is None:
            raise TypeError("key must not be None.")
        if key[0] == "@":
            self.set_special(key[1:], value)
        else:
            self.data[key] = self.wrap_value(key, value)
        self.notify()

    def get_specials(self):
        return self.data_specials

    def as_dict(self):
        result = dict(self.items())
        result.update(
            map(
                # Prepend the removed @ signs to special values
                lambda x: ("@"+x[0], x[1]),
                self.get_specials().items()
            )
        )
        return result

    def get_special(self, key, default=None):
        if default is not None and key not in self.data_specials:
            return default
        return self.data_specials[key]

    def set_special(self, key, value):
        self.data_specials[key] = value
        self.notify()

    def __repr__(self):
        def dict_repr(dict_, prefix=""):
            if prefix:
                key_repr = str
            else:
                key_repr = repr
            return ", ".join(
                [prefix + key_repr(key) + ": " + repr(dict_[key]) for key in dict_]
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
    def __init__(self, origin=None, args=[]):
        # Init fields and load data
        self.data = []
        super().__init__(origin)
        self.extend(args)

    def extend(self, args):
        self.notify_active = False
        super().extend(args)
        self.notify_active = True
        self.notify()

    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.start is not None and index.start >= self.len():
                raise IndexError()
            if index.stop is not None and index.stop >= self.len():
                raise IndexError()
            return self.__class__(self.origin, args=self.data[index])
        elif isinstance(index, int):
            if index >= self.len():
                raise IndexError()
            return self.getitem(index)
        else:
            raise TypeError(
                "'index' needs to be of type slice or int, not " +
                type(indx)
            )

    def __delitem__(self, index): self.delitem(index)
    def __iter__(self): return iter(self.data)
    def __len__(self): return self.len()

    def __mul__(self, other):
        if not isinstance(other, int):
            raise TypeError(
                "'other' needs to be of type slice or int, not " +
                type(other)
            )
        return self.data * other

    def __add__(self, other):
        new_list = self.copy()
        if isinstance(other, AutoExpandList):
            for item in other.data:
                new_list.append(item)
        elif isinstance(other, list):
            for item in other:
                new_list.append(item)
        else:
            raise TypeError(
                "'other' needs to be of type list or AutoExpandList, not " +
                type(other)
            )
        return new_list

    def __eq__(self, other):
        if len(self) == len(other):
            same = True
            for i, item in enumerate(self):
                same = same and item == other[i]
            return same
        return False

    def __setitem__(self, value):
        self.data.append(self.wrap_value(self.len(), value))
        self.notify()

    def insert(self, index, value):
        self.data.insert(index, self.wrap_value(index, value))
        self.notify()

    def __repr__(self):
        rep = type(self).__name__ + "["
        for item in self.data[:-1]:
            rep += repr(item) + ", "
        if self.len():
            rep += repr(self.data[-1])
        rep += "]"
        return rep


class AutoExpanderJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AutoExpandDict):
            return obj.as_dict()
        if isinstance(obj, AutoExpandList):
            return list(obj)
        return super().default(obj)


class StaticAutoExpandDict(AutoExpandDict):
    def __setitem__(self, key, value):
        if key in self:
            super().__setitem__(key, value)
        else:
            raise UberdotError(
                "Can't create new key '" + key + "' in a StaticAutoExpandDict"
            )

class LinkData(StaticAutoExpandDict):
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
        self.data["modified"] = None
        # Creation date of link itself
        self.data["created"] = None

    @classmethod
    def from_file(cls, path):
        if not os.path.exists(path):
            raise FileNotFoundError
        props = {}
        props["path"] = path
        props["permission"] = utils.get_permission(path)
        props["modified"] = utils.timestamp_to_string(os.path.getmtime(path))
        props["created"] = utils.timestamp_to_string(os.path.getctime(path))
        props["owner"] = utils.ids_to_owner_string(utils.get_owner(path))
        props["hard"], props["target"], props["target_inode"] = utils.readlink(path)
        if not props["hard"] and os.path.exists(props["target"]):
            props["secure"] = utils.get_owner(path) == utils.get_owner(props["target"])
        return cls(args=props)

    def exists(self):
        try:
            return self.is_same_file(LinkData.from_file(self["path"]))
        except FileNotFoundError:
            return False

    def similar_exists(self):
        try:
            if self.is_similar_file(LinkData.from_file(self["path"])):
                return True
        except FileNotFoundError:
            pass
        for file in utils.listfiles(os.path.dirname(self["path"])):
            if self.is_similar_file(LinkData.from_file(file)):
                return True
        return False

    def is_similar_file(self, link):
        if self["path"] == link["path"]:
            return True
        if self["target"] is not None and link["target"] is not None:
            if self["target"] == link["target"]:
                return True
        return self["target_inode"] == link["target_inode"]

    def is_same_file(self, link):
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

    def __eq__(self, link):
        return self.is_same_file(link) and self["buildup"] == link["buildup"]

    def wrap_value(self, key, value, for_state_version=False):
        if key == "buildup":
            if for_state_version:
                value = BuildupData.wrap_buildup_state(value, self.origin)
            else:
                value = BuildupData.wrap_buildup_gen(value)
        return super().wrap_value(key, value)


class StateLinkData(LinkData):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args=args, **kwargs)
        self.expander["path"] = AutoExpander.abspath(origin)
        self.expander["target"] = AutoExpander.abspath(origin)
        self.expander["owner"] = utils.inflate_owner

    def __eq__(self, link):
        result = super().__eq__(link)
        if type(link) in [StateLinkData, GenLinkData]:
            result = result and self["buildup"] == link["buildup"]
        return result

    def wrap_value(self, key, value):
        return super().wrap_value(key, value, for_state_version=True)


class GenLinkData(LinkData):
    def __init__(self, args={}, **kwargs):
        super().__init__(args=args, **kwargs)
        self.expander["owner"] = utils.inflate_owner

    def init_data(self):
        super().init_data()
        # Automatically set modification and creation dates since this
        # data structure represents freshly generated links
        self.data["created"] = utils.get_date_time_now()
        self.data["modified"] = self.data["created"]

    def __eq__(self, link):
        result = super().__eq__(link)
        if type(link) in [StateLinkData, GenLinkData]:
            result = result and self["buildup"] == link["buildup"]
        return result

    def wrap_value(self, key, value):
        return super().wrap_value(key, value, for_state_version=False)


class BuildupData(AutoExpandDict):
    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None

    def __eq__(self, buildup):
        return all(map(
            lambda x: x in self and x in buildup and self[x] == buildup[x],
            set(list(self.keys()) + list(buildup.keys()))
        ))

    @staticmethod
    def gen_type_error(value, supported_types):
        type_names = map(lambda x : x.__name__, supported_types)
        if not any(map(lambda x : isinstance(value, x), supported_types)):
            raise TypeError(
                "value needs to be of type " + ", ".join(type_names) +
                ", list or dict, not " + type(value).__name__
            )

    @staticmethod
    def wrap_buildup_gen(value):
        if type(value) == dict and "type" in value:
            if value["type"] == "StaticFile":
                value = GenCopyData(args=value)
            else:
                value = GenBuildupData(args=value)
        elif type(value) == list:
            value = GenBuildupList(args=value)
        else:
            BuildupData.gen_type_error(
                value, [type(None), GenCopyData, GenBuildupData, GenBuildupList]
            )
        return value

    @staticmethod
    def wrap_buildup_state(value, origin):
        if type(value) == dict and "type" in value:
            if value["type"] == "StaticFile":
                value = StateCopyData(origin, args=value)
            else:
                value = StateBuildupData(origin, args=value)
        elif type(value) == list:
            value = StateBuildupList(origin, args=value)
        else:
            BuildupData.gen_type_error(
                value, [type(None), StateCopyData, StateBuildupData, StateBuildupList]
            )
        return value

    def wrap_value(self, key, value, for_state_version=False):
        if key == "source":
            if for_state_version:
                value = BuildupData.wrap_buildup_state(value, self.origin)
            else:
                value = BuildupData.wrap_buildup_gen(value)
        return super().wrap_value(key, value)


class GenBuildupList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = BuildupData.wrap_buildup_gen(value)
        return super().wrap_value(key, value)


class StateBuildupList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = BuildupData.wrap_buildup_state(value, self.origin)
        return super().wrap_value(key, value)


class StateBuildupData(BuildupData):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args=args, **kwargs)
        self.expander["path"] = AutoExpander.abspath(origin)

    def wrap_value(self, key, value):
        return super().wrap_value(key, value, for_state_version=True)


class GenBuildupData(BuildupData):
    def __init__(self, args={}, **kwargs):
        super().__init__(args=args, **kwargs)

    def wrap_value(self, key, value):
        return super().wrap_value(key, value, for_state_version=False)


# class StateSplittedFileBuildupData(StateBuildupData):
#     def init_data(self):
#         super().init_data()
#         self.data["file_lengths"] = []


# class GenSplittedFileBuildupData(GenBuildupData):
#     def init_data(self):
#         super().init_data()
#         self.data["file_lengths"] = []


class CopyData(StaticAutoExpandDict):
    def init_data(self):
        self.data["path"] = None
        self.data["source"] = None
        self.data["type"] = None


class StateCopyData(CopyData):
    def __init__(self, origin, args={}, **kwargs):
        super().__init__(origin, args=args, **kwargs)
        self.expander["path"] = AutoExpander.abspath(origin)
        self.expander["source"] = AutoExpander.abspath(origin)


class GenCopyData(CopyData):
    def __init__(self, args={}, **kwargs):
        super().__init__(args=args, **kwargs)


class ProfileData(AutoExpandDict):
    def __init__(self, origin=None, args={}, **kwargs):
        super().__init__(origin, args=args, **kwargs)
        self.expander["beforeInstall"] = ProfileData.expand_event(self["name"], "beforeInstall")
        self.expander["beforeUpdate"] = ProfileData.expand_event(self["name"], "beforeUpdate")
        self.expander["beforeUninstall"] = ProfileData.expand_event(self["name"], "beforeUninstall")
        self.expander["afterInstall"] = ProfileData.expand_event(self["name"], "afterInstall")
        self.expander["afterUpdate"] = ProfileData.expand_event(self["name"], "afterUpdate")
        self.expander["afterUninstall"] = ProfileData.expand_event(self["name"], "afterUninstall")

    @staticmethod
    def expand_event(profilename, eventname):
        def expand_func(value):
            if not re.match("[a-f0-9]{32}", value, re.I):
                return value
            return utils.abspath(
                "scripts/" + profilename + "_" + eventname + "_" + value + ".sh",
                origin=const.internal.session_dir
            )
        return expand_func

    def init_data(self):
        self.data["name"] = None
        self.data["parent"] = None
        self.data["beforeInstall"] = None
        self.data["beforeUpdate"] = None
        self.data["beforeUninstall"] = None
        self.data["afterInstall"] = None
        self.data["afterUpdate"] = None
        self.data["afterUninstall"] = None


class StateProfileData(ProfileData):
    def init_data(self):
        super().init_data()
        self.data["links"] = StateLinkDataList(self.origin)
        self.data["installed"] = None
        self.data["updated"] = None

    def wrap_value(self, key, value):
        if key == "links" and not isinstance(value, StateLinkDataList):
            value = StateLinkDataList(self.origin, value)
        return super().wrap_value(key, value)


class GenProfileData(ProfileData):
    def init_data(self):
        super().init_data()
        self.data["links"] = GenLinkDataList()
        self.data["profiles"] = []

    def wrap_value(self, key, value):
        if key == "links" and not isinstance(value, GenLinkDataList):
            value = GenLinkDataList(value)
        return super().wrap_value(key, value)


class GenLinkDataList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = GenLinkData(value)
        return super().wrap_value(key, value)


class StateLinkDataList(AutoExpandList):
    def wrap_value(self, key, value):
        if type(value) == dict:
            value = StateLinkData(self.origin, value)
        return super().wrap_value(key, value)


###############################################################################
# Main classes
###############################################################################

class GlobalState(metaclass=utils.Singleton):
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
            state = ForeignState.from_file(path)
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
        self.origin = os.path.dirname(file)
        self.file = file
        # Load state files of current user
        log_debug("Loading state file '" + self.file + "'.")
        try:
            self.state_raw = json.load(open(self.file))
        except json.decoder.JSONDecodeError as err:
            raise PreconditionError(
                "Can not parse json in '" + self.file + "'. " + str(err)
            )
        except FileNotFoundError:
            raise PreconditionError(
                "State file '" + self.file + "' doesn't exist."
            )
        self.auto_write = False
        # Upgrade
        self._upgrade()
        # Load upgraded raw json into AutoExpandDict
        try:
            super().__init__(self.origin, args=self.state_raw)
        except UberdotError as err:
            raise PreconditionError(
                "Can not parse state file data of '" +
                self.file + "'. " + str(err._message)
            )
        log_debug("Checking state file consistency.")
        self.check_empty_fields()
        # Setup saving mechanism
        self.auto_write = auto_write


    def check_empty_fields(self):
        # Checks if all fields that have to be set, are set
        for profile in self.values():
            for link in profile["links"]:
                for key, val in link.items():
                    if key in ["target_inode", "buildup"]:
                        continue
                    msg = "'" + key + "' is None in state file '"
                    msg += self.file + "'."
                    if val is None:
                        raise PreconditionError(msg)


    @classmethod
    def from_timestamp(cls, timestamp):
        return cls(utils.build_statefile_path(timestamp))

    @staticmethod
    def from_timestamp_before(timestamp):
        for n, file in enumerate(State._get_snapshots(const.session_dir)):
            if int(utils.get_timestamp_from_path(file)) > int(timestamp):
                break
        return State.fromIndex(n-1)

    @classmethod
    def from_file(cls, file):
        return cls(file)

    @staticmethod
    def from_number(number):
        return State.fromIndex(number-1)

    @staticmethod
    def from_index(index):
        file = State._get_snapshots(const.session_dir)[index]
        return State.fromFile(file)

    @classmethod
    def current(cls):
        path = utils.build_statefile_path()
        if not os.path.exists(path):
            log_debug("No state file found. Creating new.")
            utils.makedirs(os.path.dirname(path))
            file = open(path, "w")
            file.write('{"@version": "' + const.internal.VERSION + '"}')
            file.close()
        return cls(path, auto_write=True)

    def get_snapshots(self):
        return utils.find_snapshots(self.origin)

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
            if patch[1] is None:
                if patch[2] is None:
                    msg = "Can't upgrade to version " + patch[0] + ". "
                    msg += "Manual upgrade by the user required."
                    raise PreconditionError(msg)
                else:
                    raise PreconditionError(patch[2])
            try:
                self.state_raw = patch[1](deepcopy(self.state_raw), self.file)
                self.state_raw["@version"] = patch[0]
            except CustomError:
                if patch[2] is None:
                    raise
                else:
                    raise PreconditionError(patch[2])
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
        if not extended_logging and patches:
            log_debug("Done.")
        # Update version number
        self.state_raw["@version"] = const.internal.VERSION

    def create_snapshot(self):
        path, ext = os.path.splitext(self.file)
        timestamp = utils.get_timestamp_now()
        path += "_" + timestamp + ext
        log_debug("Creating state file snapshot at '" + path + "'.")
        self.set_special("snapshot", timestamp)
        self.write_file(path)
        return timestamp

    def write_file(self, path=None):
        # Prepare directory
        if path is None:
            path = self.file
        utils.makedirs(os.path.dirname(path))
        # Write content to file
        try:
            file = open(path, "w")
            file.write(
                json.dumps(self.as_dict(), cls=AutoExpanderJSONEncoder, indent=4)
            )
        except OSError as err:
            msg = "An unkown error occured when trying to "
            msg += "write changes back to the state file."
            raise UnkownError(err, msg)
        finally:
            file.close()

    def wrap_value(self, key, value):
        if type(value) == dict:
            value = StateProfileData(self.origin, value)
        return super().wrap_value(key, value)

    def _notify(self):
        if self.auto_write:
            log_debug("Saving changes to current state file.")
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
