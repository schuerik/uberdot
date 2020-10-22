"""
This module contains all the different Interpreters.
Interpreters interprete all or a subset of operations of a DiffLog.
That way interpreters encapsulate behavior for checks and actions of
operations, that can be turned on and off freely.

Interpreters work by implementing callbacks that can review a single
operation. When an interpreter gets executed on a DiffLog all operations
of the DiffLog will be fed one by one into the interpreter. Most of the
interpreters will just raise an exception when they detect an issue in one
operation, some just print the operations and others can rewrite the entire
DiffLog.

.. autosummary::
    :nosignatures:

    CheckDiffsolverResultInterpreter
    CheckDynamicFilesInterpreter
    CheckFileOverwriteInterpreter
    CheckLinkBlacklistInterpreter
    CheckLinkDirsInterpreter
    CheckLinksInterpreter
    CheckProfilesInterpreter
    DUIStrategyInterpreter
    DetectRootInterpreter
    EventExecInterpreter
    EventInterpreter
    EventPrintInterpreter
    ExecuteInterpreter
    GainRootInterpreter
    Interpreter
    PrintInterpreter
    PrintPlainInterpreter
    PrintSummaryInterpreter
    RootNeededInterpreter
    SkipRootInterpreter
"""

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


import grp
import hashlib
import logging
import os
import pwd
import re
import sys
import time
from abc import abstractmethod
from inspect import getsource
from queue import Queue
from shutil import copyfile
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import Popen
from threading import Thread
from uberdot.utils import *
from uberdot.state import GlobalState


const = Const()
globalstate = GlobalState()


class Interpreter():
    """Base-class for interpreters.

    Attributes:
        data (list): The raw DiffLog that is interpreted.
            Only needed by Interpreters that alter the DiffLog.
    """
    def __init__(self):
        """Constructor"""
        self.data = None

    def set_difflog_data(self, data):
        """Sets the raw DiffLog content.

        Needed by Interpreters that alter the DiffLog.

        Args:
            data (list): The raw DiffLog that will be set
        """
        self.data = data

    def call_operation(self, operation):
        """Call the implemented behavior for this operation.

        This calls a function named like ``operation["operation"]`` with
        the prefix '_op_', if the function was implemented by the interpreter.

        Args:
            operation (dict): A operation from DiffLog
        """
        # Check if this interpreter has implemented the operation, then call
        attribute = getattr(self, "_op_" + operation["operation"], None)
        if callable(attribute):
            attribute(operation)
        else:
            # Check if this interpreter has implemented _op_fallback, then call
            attribute = getattr(self, "_op_fallback", None)
            if callable(attribute):
                attribute(operation)


class PrintPlainInterpreter(Interpreter):
    """Prints add/remove/update-operation without any formating."""
    def __init__(self):
        """Constructor.

        Maps ``_op_*`` functions to ``print()``.
        """
        super().__init__()
        self._op_fallback = print


class PrintSummaryInterpreter(Interpreter):
    def __init__(self):
        super().__init__()
        self.profile_changes = {}
        self._op_add_l = self.gen_counter("added")
        self._op_remove_l = self.gen_counter("removed")
        self._op_update_l = self.gen_counter("updated")
        self._op_track_l = self.gen_counter("tracked")
        self._op_untrack_l = self.gen_counter("untracked")
        self._op_restore_l = self.gen_counter("restored")
        self._op_update_prop = self.gen_counter("updated properties")
        self._op_update_t = self.gen_counter("updated")

    def gen_counter(self, key):
        def counter(dop):
            prof = dop["profile"]
            if prof not in self.profile_changes:
                self.profile_changes[prof] = {
                    "added": 0,
                    "removed": 0,
                    "updated": 0,
                    "tracked": 0,
                    "untracked": 0,
                    "restored": 0,
                    "updated properties": 0
                }
            self.profile_changes[prof][key] +=1
        return counter

    def _op_fin(self, dop):
        for profile in self.profile_changes:
            changes = dict(filter(lambda x: x[1] > 0, self.profile_changes[profile].items()))
            changes = ", ".join(map(lambda x: str(x[1]) + " " + x[0], changes.items()))
            log_operation(profile, changes)
        if not self.profile_changes:
            log("Already up-to-date.")


class PrintInterpreter(Interpreter):
    """Pretty-prints log messages and what a operation is going to do."""

    def _op_info(self, dop):
        """Logs/Prints out an info-operation.

        Args:
            dop (dict): The info-operation that will be logged
        """
        log_operation(dop["profile"], dop["message"])

    def _op_add_p(self, dop):
        """Logs/Prints out that a profile was added.

        Args:
            dop (dict): The add-operation that will be logged
        """
        if dop["parent"] is not None:
            log_operation(dop["profile"], "Installing new profile as" +
                          " subprofile of " + dop["parent"])
        else:
            log_operation(dop["profile"], "Installing new profile")

    def _op_remove_p(self, dop):
        """Logs/Prints out that a profile was removed.

        Args:
            dop (dict): The remove-operation that will be logged
        """
        log_operation(dop["profile"], "Uninstalled profile")

    def _op_untrack_l(self, dop):
        """Logs/Prints out that a link won't be tracked anymore.

        Args:
            dop (dict): The forget-operation that will be logged
        """
        log_operation(
            dop["profile"], "Stop tracking '" + dop["symlink"]["path"] + "'"
        )

    def _op_track_l(self, dop):
        """Logs/Prints out that a link will be tracked now.

        Args:
            dop (dict): The track-operation that will be logged
        """
        log_operation(
            dop["profile"], "Tracking '" + dop["symlink"]["path"] + "' now"
        )

    def _op_update_p(self, dop):
        """Logs/Prints out that a profile was updated.

        Args:
            dop (dict): The update-operation that will be logged
        """
        log_operation(dop["profile"], "Profile updated")

    def _op_add_l(self, dop):
        """Logs/Prints out that a link was added.

        Args:
            dop (dict): The add-operation that will be logged
        """
        target_str = dop["symlink"]["target"]
        if dop["symlink"]["buildup"] is not None:
            if dop["symlink"]["buildup"]["type"] == "StaticFile":
                target_str = "a copy of " + dop["symlink"]["buildup"]["source"]
        log_operation(dop["profile"], dop["symlink"]["path"] +
                      " was created and links to " + target_str)

    def _op_remove_l(self, dop):
        """Logs/Prints out that a link was removed.

        Args:
            dop (dict): The remove-operation that will be logged
        """
        log_operation(dop["profile"], dop["symlink"]["path"] +
                      " was removed from the system")

    def _op_update_l(self, dop):
        """Logs/Prints out that a link was updated.

        The message is generated according to what changed in the updated link.

        Args:
            dop (dict): The update-operation that will be logged
        """
        if dop["symlink1"]["path"] != dop["symlink2"]["path"]:
            log_operation(dop["profile"], dop["symlink1"]["path"] +
                          " was moved to " + dop["symlink2"]["path"])
        elif dop["symlink2"]["target"] != dop["symlink1"]["target"]:
            log_operation(dop["profile"], dop["symlink1"]["path"] +
                          " points now to " + dop["symlink2"]["target"])
        else:
            msg_start = dop["symlink1"]["path"] + " has changed "
            if dop["symlink2"]["permission"] != dop["symlink1"]["permission"]:
                msg = msg_start + "permission from "
                msg += str(dop["symlink1"]["permission"])
                msg += " to " + str(dop["symlink2"]["permission"])
                log_operation(dop["profile"], msg)
            if dop["symlink1"]["owner"] != dop["symlink2"]["owner"]:
                msg = msg_start + "owner from " + dop["symlink1"]["owner"]
                msg += " to " + dop["symlink2"]["owner"].split(":")
                log_operation(dop["profile"], msg)
            if dop["symlink2"]["secure"] != dop["symlink1"]["secure"]:
                msg = msg_start + "secure feature from "
                msg += "enabled" if dop["symlink1"]["secure"] else "disabled"
                msg += " to "
                msg += "enabled" if dop["symlink2"]["secure"] else "disabled"
                log_operation(dop["profile"], msg)

    def _op_update_prop(self, dop):
        if dop["key"] == "parent":
            if dop["value"] is None:
                log_operation(dop["profile"], "Is root profile now")
            else:
                log_operation(dop["profile"],
                              "Is subprofile of '" + dop["value"] + "' now")
        else:
            if dop["value"] is None:
                log_operation(
                    dop["profile"],
                    "Unset '" + dop["key"] + "'.",
                    debug=True
                )
            else:
                log_operation(
                    dop["profile"],
                    "Set '" + dop["key"] + "' to '" + str(dop["value"]) + "'",
                    debug=True
                )

    def _op_restore_l(self, dop):
        log_operation(
            dop["profile"],
            "Restored tracked file '" + dop["saved_link"]["path"] + "'"
        )

    def _op_update_t(self, dop):
        log_operation(
            dop["profile"],
            "Updating record of '" + dop["symlink1"]["path"] + "'"
        )


class DUIStrategyInterpreter(Interpreter):
    """Reorders DiffLog so linking won't be in the order of profiles but
    instead in the order Delete-Update-Insert. It also removes log messages
    because without the old order they are not useful anymore.

    Attributes:
        profile_deletes (list): A collection of profile-remove-operations
        profile_updates (list): A collection of profile-update-operations
        profile_adds (list): A collection of profile-add-operations
        link_deletes (list): A collection of link-remove-operations
        link_updates (list): A collection of link-update-operations
        link_adds (list): A collection of link-add-operations
    """
    def __init__(self):
        super().__init__()
        self.profile_deletes = []
        self.profile_updates = []
        self.profile_adds = []
        self.link_deletes = []
        self.link_updates = []
        self.link_adds = []
        self.property_updates = []

    def _op_start(self, dop):
        log_debug("Reordering operations to use DUI-strategy.")

    def _op_add_p(self, dop):
        """Adds the profile-add-operation to ``profile_adds``.

        Args:
            dop (dict): The operation that will be added
        """
        self.profile_adds.append(dop)

    def _op_track_l(self, dop):
        self.link_adds.append(dop)

    def _op_update_t(self, dop):
        self.link_updates.append(dop)

    def _op_remove_p(self, dop):
        """Adds the profile-remove-operation to ``profile_removes``.

        Args:
            dop (dict): The operation that will be added
        """
        self.profile_deletes.append(dop)

    def _op_untrack_l(self, dop):
        self.link_deletes.append(dop)

    def _op_restore_l(self, dop):
        self.link_updates.append(dop)

    def _op_update_p(self, dop):
        """Adds the profile-update-operation to ``profile_updates``.

        Args:
            dop (dict): The operation that will be added
        """
        self.profile_updates.append(dop)

    def _op_add_l(self, dop):
        """Adds the link-add-operation to ``link_adds``.

        Args:
            dop (dict): The operation that will be added
        """
        self.link_adds.append(dop)

    def _op_remove_l(self, dop):
        """Adds the link-remove-operation to ``link_removes``.

        Args:
            dop (dict): The operation that will be added
        """
        self.link_deletes.append(dop)

    def _op_update_l(self, dop):
        """Adds the link-update-operation to ``link_updates``.

        Args:
            dop (dict): The operation that will be added
        """
        self.link_updates.append(dop)

    def _op_update_prop(self, dop):
        self.property_updates.append(dop)

    def _op_fin(self, dop):
        """Merges the collections of operations in the correct order
        and overwrites ``self.data`` to alter the DiffLog

        Args:
            dop (dict): Unused in this implementation
        """
        merged_list = self.link_deletes + self.profile_deletes
        merged_list += self.profile_updates + self.link_updates
        merged_list += self.profile_adds + self.link_adds
        merged_list += self.property_updates
        self.data.clear()
        for item in merged_list:
            self.data.append(item)


class CheckDynamicFilesInterpreter(Interpreter):
    """Checks if there are changes to a dynamic file and
    prevents overwrites of these files.

    Attributes:
        change_detected (bool): Stores, if a change was dected in any dynamic file
    """
    def __init__(self):
        self.change_detected = False
        super().__init__()

    def _op_update_l(self, dop):
        """Inspects the target file of the to be updated link.

        Args:
            dop (dict): The update-operation of the to be updated link
        """
        self.inspect_file(dop["symlink1"]["target"])

    def _op_remove_l(self, dop):
        """Inspects the target file of the to be removed link.

        Args:
            dop (dict): The remove-operation of the to be removed link
        """
        self.inspect_file(dop["symlink"]["target"])

    def _op_restore_l(self, dop):
        """Inspects the target file of the to be restored link.

        Args:
            dop (dict): The remove-operation of the to be removed link
        """
        self.inspect_file(dop["saved_link"]["target"])

    # TODO: Inspect file on other operations?

    def inspect_file(self, target):
        """Checks if a file is dynamic and was changed. If so, it
        calls a small UI to store/undo changes.

        Args:
            target (str): The full path to the file that will be checked
        """
        print(target)
        if not is_dynamic_file(target):
            # This is not a dynamic file
            return
        print(target)
        # Calculate new hash and get old has of file
        md5_calc = md5(open(target, "rb").read())
        md5_old = os.path.basename(target)[-32:]
        # Check for changes
        if md5_calc != md5_old:
            log_warning("You made changes to '" + target + "'.")
            self.change_detected = True

    def _op_fin(self, dop):
        if self.change_detected:
            msg = "Changes to your files would be lost otherwise, so you"
            msg += " need to run 'udot sync' to merge or discard changes "
            msg += "before you proceed."
            raise PreconditionError(msg)


class CheckLinksInterpreter(Interpreter):
    """Checks for conflicts between all links.

    Conflicts are things like duplicates, multiple targets / overwrites, etc.

    Args:
        linklist (list): list that stores all links, their corresponding
            profiles and if they are already installed. Links that are already
            installed and won't be removed, will end up twice in this list.
    """
    def __init__(self):
        """Constructor.

        Initializes ``linklist`` with all links from the state file.

        Args:
            state (State): The state file, that was used to create the
                current DiffLog
        """
        super().__init__()
        # Setup linklist to store/lookup which links are modified
        # Stores for any link: (linkname, profile, user, is_installed)
        self.linklist = []
        for user, profile in globalstate.get_profiles():
            for link in profile["links"]:
                self.linklist.append((link["path"], profile["name"], user, True))
        # Track and untrack do the same as add and remove
        self._op_track_l = self._op_add_l
        self._op_untrack_l = self._op_remove_l

    def _op_add_l(self, dop):
        """Checks if the to be added link already occurs in ``linklist``.

        This would be forbidden, because a link that is already installed can't
        be added again (only updated). Similary it would be forbidden to add a
        link that was already added by another profile in the same run.
        If everything is valid, the link will be added to the list.

        Args:
            dop (dict): The add-operation that will be checked
        Raises:
            IntegrityError: The check failed
        """
        self.add(dop["symlink"]["path"], dop["profile"])

    def _op_update_l(self, dop):
        self.remove(dop["symlink1"]["path"])
        self.add(dop["symlink2"]["path"], dop["profile"])

    def _op_remove_l(self, dop):
        """Removes link from linklist because links could be removed and
        added in one run by different profiles.

        In that case it would look like the link is added even though it is
        already installed if we don't remove it here.

        Args:
            dop (dict): The remove-operation that will be used to remove the
                link
        """
        self.remove(dop["symlink"]["path"])

    def add(self, name, profile):
        for item in self.linklist:
            if item[0] == name:
                if item[3]:
                    msg = " installed "
                else:
                    msg = " defined "
                user_msg = "of user " + item[2] if item[2] != const.internal.user else ""
                msg = "The link '" + name + "' is already" + msg + "by '"
                msg += item[1] + "' " + user_msg + "and would be overwritten by '"
                msg += profile + "'. In some cases this error can be "
                msg += "fixed by setting the --dui flag."
                raise IntegrityError(msg)
        self.linklist.append((name, profile, const.internal.user, False))

    def remove(self, name):
        for item in self.linklist:
            if item[0] == name:
                self.linklist.remove(item)
                return


class CheckLinkBlacklistInterpreter(Interpreter):
    """Checks if a operation touches a link that is on the blacklist.

    Attributes:
        blacklist (list): A list of file name patterns that are forbidden
            to touch without superforce flag
    """
    def __init__(self, superforce):
        """Constructor.

        Loads the blacklist.
        """
        super().__init__()
        self.superforce = superforce
        self.blacklist = []
        search_paths = [const.internal.data_dir]
        search_paths += const.internal.cfg_search_paths
        for blfile in find_file_at("black.list", search_paths):
            with open(blfile, "r") as file:
                for line in file.readlines():
                    self.blacklist.append(line)
        self.blacklist = [entry.strip() for entry in self.blacklist]
        self.blacklist = list(set(self.blacklist))

    def check_blacklist(self, file_name, action):
        """Checks if a file matches a pattern in the blacklist.

        Args:
            file_name (str): Name of the file
            action (str): The action that is causing the touch of the file
        Raises:
            UserAbortion: The user decided to not touch the file
            IntegrityError: The file was blacklisted and ``superforce`` wasn't
                set
        """
        for entry in self.blacklist:
            if re.fullmatch(entry, file_name):
                log_warning("You are trying to " + action + " '" + file_name +
                            "' which is blacklisted. It is considered " +
                            "dangerous to " + action + " those files!")
                if self.superforce:
                    user_confirmation("YES")
                else:
                    log_warning("If you really want to modify this file" +
                                " you can use the --superforce flag to" +
                                " ignore the blacklist.")
                    raise IntegrityError("Won't " + action +
                                         " blacklisted file!")

    def _op_update_l(self, dop):
        """Checks the old and the new symlink for blacklist violations.

        Args:
            dop (dict): The update-operation whose symlinks will be checked
        """
        if dop["symlink1"]["path"] == dop["symlink2"]["path"]:
            self.check_blacklist(dop["symlink1"]["path"], "update")
        else:
            self.check_blacklist(dop["symlink1"]["path"], "remove")
            self.check_blacklist(dop["symlink2"]["path"], "overwrite")

    def _op_remove_l(self, dop):
        """Checks the to be removed symlink for blacklist violations.

        Args:
            dop (dict): The remove-operation whose symlink will be checked
        """
        self.check_blacklist(dop["symlink"]["path"], "remove")

    def _op_add_l(self, dop):
        """Checks the to be added symlink for blacklist violations.

        Args:
            dop (dict): The add-operation whose symlink will be checked
        """
        self.check_blacklist(dop["symlink"]["path"], "overwrite")

    def _op_restore_l(self, dop):
        self.check_blacklist(dop["saved_link"]["path"], "overwrite")
        self.check_blacklist(dop["actual_link"]["path"], "remove")


class CheckLinkDirsInterpreter(Interpreter):
    """Checks if directories need to be created.

    Attributes:
        makedirs (bool): Stores, if ``--makedirs`` was set
    """
    def __init__(self, makedirs):
        """Constructor. """
        super().__init__()
        self.makedirs = makedirs

    def _op_add_l(self, dop):
        """Checks if the directory of the to be added link already exists.

        Args:
            dop (dict): The add-operation whose symlink will be checked
        """
        self.check_dirname(os.path.dirname(dop["symlink"]["path"]))

    def _op_restore_l(self, dop):
        self.check_dirname(os.path.dirname(dop["saved_link"]["path"]))

    def _op_update_l(self, dop):
        """Checks if the directory of the to be updated link already exists.

        Args:
            dop (dict): The update-operation whose symlink will be checked
        """
        self.check_dirname(os.path.dirname(dop["symlink2"]["path"]))

    def check_dirname(self, dirname):
        """Checks if a directory exists.

        Args:
            dirname (str): The path to a directory
        Raises:
            PreconditionError: The directory doesn't exist and ``makedirs``
                isn't set
        """
        if not self.makedirs:
            if not os.path.isdir(dirname):
                msg = "The directory '" + dirname + "/' needs to be created "
                msg += "in order to perform this action, but "
                msg += "--makedirs is not set"
                raise PreconditionError(msg)


class CheckDiffsolverResultInterpreter(Interpreter):
    """Checks if operations meet the implicated constraints. For example
    if a remove operation for a specific path is in the difflog the file
    needs to exist. Otherwise it should have been an untrack operation.
    """
    def __init__(self, error_type=FatalError):
        self.state = globalstate.current
        self.error_type = error_type
        self.removed_links = []

    def _raise(self, msg):
        log_debug("\n".join([repr(x) for x in self.data]))
        raise self.error_type(msg)

    def _op_fallback(self, dop):
        if dop["operation"] not in ["start", "fin", "info"]:  # pragma: no cover
            # This is always a FatalError
            raise FatalError("No check implemented for " + dop["operation"])

    def is_link_in_state(self, profilename, link):
        if profilename not in self.state:
            return False
        for state_link in self.state[profilename]["links"]:
            if state_link == link:
                return link["path"] not in self.removed_links
        return False

    def _op_update_t(self, dop):
        if not self.is_link_in_state(dop["profile"], dop["symlink1"]):  # pragma: no cover
            msg = "The record of '" + dop["symlink1"]["path"] + "' can not be updated "
            msg += " because there is no such record."
            self._raise(msg)
        if not dop["symlink2"].exists():  # pragma: no cover
            msg = "The record of '" + dop["symlink1"]["path"] + "' can not be updated "
            msg += " because the link doesn't exist."
            self._raise(msg)

    def _op_restore_l(self, dop):
        # Only restore link if it is tracked and differs from the tracked
        if not self.is_link_in_state(dop["profile"], dop["saved_link"]):  # pragma: no cover
            msg = "'" + dop["saved_link"]["path"] + "' can not be restored "
            msg += " because it is not tracked."
            self._raise(msg)
        if dop["saved_link"].exists():  # pragma: no cover
            msg = "'" + dop["saved_link"]["path"] + "' can not be restored "
            msg += " because it already exists like this."
            self._raise(msg)

    def _op_untrack_l(self, dop):
        # Only untrack link if it is tracked
        if not self.is_link_in_state(dop["profile"], dop["symlink"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' is not tracked."
            self._raise(msg)
        self.removed_links.append(dop["symlink"]["path"])

    def _op_track_l(self, dop):
        # Only track link if it exists and is not already tracked
        if not os.path.lexists(dop["symlink"]["path"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' can not be tracked "
            msg += " because it does not exist."
            self._raise(msg)
        if self.is_link_in_state(dop["profile"], dop["symlink"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' is already tracked."
            self._raise(msg)

    def _op_remove_l(self, dop):
        # Only remove symlink if it still exists and is tracked
        if not os.path.lexists(dop["symlink"]["path"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' can not be removed because"
            msg += " it does not exist."
            self._raise(msg)
        if not self.is_link_in_state(dop["profile"], dop["symlink"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' is not tracked, so it can't be removed."
            self._raise(msg)
        self.removed_links.append(dop["symlink"]["path"])

    def _op_update_l(self, dop):
        # Only update link if old link still exists, the target of the
        # new link exists, the old link is tracked and the links differ
        if not os.path.lexists(dop["symlink1"]["path"]):  # pragma: no cover
            msg = "'" + dop["symlink1"]["path"] + "' can not be updated"
            msg += " because it does not exist on your filesystem."
            self._raise(msg)
        if not os.path.exists(dop["symlink2"]["target"]):  # pragma: no cover
            msg = "'" + dop["symlink1"]["path"] + "' can not be updated"
            msg += " to point to '" + dop["symlink2"]["target"] + "'"
            msg += " because '" + dop["symlink2"]["target"]
            msg += "' does not exist in your filesystem."
            self._raise(msg)
        if not self.is_link_in_state(dop["profile"], dop["symlink1"]):  # pragma: no cover
            msg = "'" + dop["symlink1"]["path"] + "' is not tracked, so can't update here."
            self._raise(msg)
        if dop["symlink1"] == dop["symlink2"]:  # pragma: no cover
            self._raise("New symlink is the same as the old symlink, so update is pointless.")
        if dop["symlink1"]["path"] != dop["symlink2"]["path"]:  # pragma: no cover
            self.removed_links.append(dop["symlink1"]["path"])

    def _op_add_l(self, dop):
        # Only create symlink if is not already tracked and only if
        # the file it points to exists
        if not os.path.exists(dop["symlink"]["target"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' will not be created"
            msg += " because it points to '" + dop["symlink"]["target"]
            msg += "' which does not exist in your filesystem."
            self._raise(msg)
        if self.is_link_in_state(dop["profile"], dop["symlink"]):  # pragma: no cover
            msg = "'" + dop["symlink"]["path"] + "' is already tracked."
            self._raise(msg)

    def _op_add_p(self, dop):
        # Only add profile if it wasn't installed
        if dop["profile"] in self.state:  # pragma: no cover
            msg = "Profile '" + dop["profile"] + "' is already installed."
            self._raise(msg)

    def _op_update_p(self, dop):
        # Only update profile if it was in installed
        if dop["profile"] not in self.state:  # pragma: no cover
            msg = "Profile '" + dop["profile"] + "' is not installed."
            self._raise(msg)

    def _op_remove_p(self, dop):
        # Only remove profile if it was in installed
        if dop["profile"] not in self.state:  # pragma: no cover
            msg = "Profile '" + dop["profile"] + "' is not installed."
            self._raise(msg)

    def _op_update_prop(self, dop):
        # Only update property if changed
        msg = "Property '" + dop["key"] + "' of profile '"
        msg += dop["profile"] + "' did not change."
        if dop["profile"] not in self.state:
            return
        profile = self.state[dop["profile"]]
        if dop["key"] in profile:
            if dop["value"] == profile[dop["key"]]:  # pragma: no cover
                self._raise(msg)
        else:
            if dop["value"] is None:  # pragma: no cover
                self._raise(msg)


class CheckFileOverwriteInterpreter(Interpreter):
    """Checks if links would overwrite existing files.

    Attributes:
        removed_links (list): A collection of all links that are going to be
            removed
    """
    def __init__(self, force):
        """Constructor"""
        super().__init__()
        self.removed_links = []
        self.force = force

    def _op_remove_l(self, dop):
        """Checks if the to be removed link really exists.

        Furthermore adds the link to ``removed_links``, because removed links
        need to be stored for ``_op_add_l()``.

        Args:
            dop (dict): The remove-operation that will be checked
        Raises:
            PreconditionError: The to be removed link does not exist
        """
        self.removed_links.append(dop["symlink"]["path"])

    def _op_untrack_l(self, dop):
        self.removed_links.append(dop["symlink"]["path"])

    def _op_update_l(self, dop):
        """Checks if the old and the new link already exist.

        Furthermore adds the old link to ``removed_links`` if old and new link
        have different names, because removed links need to be stored for
        ``_op_add_l()``.

        Args:
            dop (dict): The update-operation that will be checked
        Raises:
            PreconditionError: The old link does not exist, the new
                link already exists or the new link points to a non-existent
                file
        """
        old_name = dop["symlink1"]["path"]
        new_name = dop["symlink2"]["path"]
        if old_name != new_name:
            if new_name not in self.removed_links and os.path.lexists(new_name):
                if os.path.isdir(new_name):
                    if not self.force:
                        msg = "'" + old_name + "' can not be "
                        msg += "moved to '" + new_name + "' "
                        msg += "because it is a directory and would be "
                        msg += "overwritten. You can force to overwrite empty"
                        msg += " directories by setting the --force flag."
                        raise PreconditionError(msg)
                    if os.listdir(new_name):
                        msg = "'" + old_name + "' can not be "
                        msg += "moved to '" + new_name + "' "
                        msg += "because it is a directory and contains files"
                        msg += " that would be overwritten. Please empty the"
                        msg += " directory or remove it entirely."
                        raise PreconditionError(msg)
                elif not self.force:
                    msg = "'" + old_name + "' can not be moved to '"
                    msg += new_name + "' because it already exists"
                    msg += " on your filesystem and would be overwritten."
                    raise PreconditionError(msg)
            self.removed_links.append(old_name)

    def _op_add_l(self, dop):
        """Checks if the new link already exists.

        Args:
            dop (dict): The add-operation that will be checked
        Raise:
            PreconditionError: The new link already exists or its target does
                not exist
        """
        name = dop["symlink"]["path"]
        if name not in self.removed_links and os.path.lexists(name):
            if os.path.isdir(name):
                if not self.force:
                    msg = "'" + name + "' is a directory and would be"
                    msg += " overwritten. You can force to overwrite empty"
                    msg += " directories by setting the --force flag."
                    raise PreconditionError(msg)
                if os.listdir(name):
                    msg = "'" + name + "' is a directory and contains files"
                    msg += " that would be overwritten. Please empty the"
                    msg += " directory or remove it entirely."
                    raise PreconditionError(msg)
            elif not self.force:
                msg = "'" + name + "' already exists and would be"
                msg += " overwritten by '" + dop["symlink"]["target"]
                msg += "'. You can force to overwrite the"
                msg += " original file by setting the --force flag."
                raise PreconditionError(msg)


class CheckProfilesInterpreter(Interpreter):
    """Checks if profiles can be installed together. Protects against
    duplicates and overwrites.

    Attributes:
        profile_list (list): A list that stores all profiles, their parents
            and if they are already installed. Profiles that are still
            installed in the end, will end up twice in this list.
    """
    def __init__(self, parent):
        """Constructor.

        Initializes ``profile_list`` with all profiles from the state file.

        Args:
            state (State): The state file, that was used to create the
                DiffLog
            parent_arg (str): The value of ``--parent``
        """
        super().__init__()
        self.parent = parent
        self.profile_list = []
        # profile_list contains: (profile name, parent name, is installed)
        for profile in globalstate.current.values():
            self.profile_list.append(
                    (
                        profile["name"],
                        profile["parent"] if "parent" in profile else None,
                        True
                    )
            )

    def get_known(self, name, is_installed):
        """Returns the entry of a profile from ``profile_list``. Either for
        already installed profiles or for to be installed profiles.

        Args:
            name (str): Name of the profile
            is_installed (bool): True, for lookups of already installed
                profiles
        Returns:
            Tuple: The entry that was found in ``profile_list``. ``None`` if
            no entry was found.
        """
        for p_name, p_parent, p_installed in self.profile_list:
            if name == p_name and p_installed == is_installed:
                return (p_name, p_parent, p_installed)
        return None

    def _op_add_p(self, dop):
        """Checks if a profile is added twice.

        Adds the profile to ``profile_list`` if the operation is valid.

        Args:
            dop (dict): The add-operation that will be checked
        Raises:
            IntegrityError: A profile is added twice or is already installed
        """
        known = self.get_known(dop["profile"], False)
        if known is not None:
            if known[1] is not None:
                msg = "The profile '" + dop["profile"]
                msg += "' would be already subprofile of '" + known[1] + "'."
                raise IntegrityError(msg)
            msg = "The profile '" + dop["profile"]
            msg += "' would be already installed."
            raise IntegrityError(msg)
        if self.get_known(dop["profile"], True) is not None:
            raise FatalError("addP-operation found where" +
                             " update_p-operation was expected")
        self.profile_list.append(
            (dop["profile"], dop["parent"] if "parent" in dop else None, False)
        )

    def _op_update_p(self, dop):
        """Checks if profiles will be overwritten.

        Args:
            dop (dict): The update-operation that will be checked
        Raises:
            IntegrityError: A profile is already installed as a subprofile of
                another root profile
        """
        if self.get_known(dop["profile"], False) is not None:
            raise FatalError("The profile '" + dop["profile"] +
                             "' would be added AND updated!")
        # This will prevent overwrites of profiles. Those overwrites happen
        # when a subprofile is installed even though it was already installed
        # as subprofile of another profile.
        known = self.get_known(dop["profile"], True)
        if known is not None and "parent" in dop:  # When the parent is updated
            # Just make sure the parent is really updated
            if known[1] != dop["parent"]:
                # If the user set the new parent manually, overwrites are ok
                if self.parent == dop["parent"]:
                    return
                # Detaching a profile from a parent is also allowed
                if dop["parent"] is None:
                    return
                # Get root profile of installed profile
                while known[1] is not None:
                    known = self.get_known(known[1], True)
                old_root = known[0]
                # Get root profile of updated profile
                known = self.get_known(dop["parent"], False)
                while known[1] is not None:
                    known = self.get_known(known[1], False)
                new_root = known[0]
                if new_root != old_root:
                    msg = dop["profile"] + " is already installed as"
                    msg += " subprofile of '" + old_root + "'. You need to"
                    msg += " uninstall it first to avoid conflicts!"
                    raise IntegrityError(msg)
            else:
                raise FatalError("Updated parent of profile '" +
                                 dop["parent"] + "', but parent is the same!")


class EventInterpreter(Interpreter):
    """This interpreter is the abstract base class for interpreters that
    work with profile events. Implements _op_* depending on self.event_type.

    Attributes:
        profiles (list): A list of profiles **after** their execution.
        event_type (str): A specific type ("after" or "before") that determines
            which events this interpreter shall look for
    """

    def __init__(self, event_type):
        """Constructor.

        Sets _op_add_p and _op_update_p depending on event_type.

        Args:
            profiles (list): A list of profiles **after** their execution.
            state (State): A copy of the old state file that is used to
                lookup if a profile had Uninstall-events set
            event_type (str): A specific type ("after" or "before") that
                determines which events this interpreter shall look for
        """
        self.event_type = event_type
        self._op_add_p = self.event_handler("Install")
        self._op_update_p = self.event_handler("Update")
        self._op_remove_p = self.event_handler("Uninstall")

    @abstractmethod
    def run_script(self, script_path, profilename):
        """Used to handle script execution of an event. Depending on the
        subclass this might execute or just print out the script.

        Args:
            script_path (str): The path of the script that was generated
                for an event
            profilename (str): The name of the profile whose event is
                executed
        """
        raise NotImplementedError

    def event_handler(self, name):
        """Returns a function that can be used to interprete add_p- and
        update_p-operations.

        The returned function checks for a given operation, if the profile
        has an event set that matches event_type and event_name. If so,
        it calls start_event().

        Args:
            event_name (str): Name of the event that shall be interpreted
                by the returned function
        """
        def start(dop):
            event_name = self.event_type + name
            profile_name = dop["profile"]
            if dop[self.event_type]:
                log_operation(profile_name, "Running event " + event_name)
                if not os.path.exists(dop[self.event_type]):
                    # The script was generated in a previous run and was removed
                    # This should usually not happen, but its not an error
                    log_warning(
                        "Unfortunally the generated script was removed. Skipping."
                    )
                else:
                    self.run_script(dop[self.event_type], dop["profile"])
        return start


class EventPrintInterpreter(EventInterpreter):
    """This interpreter is used to print out what an event will do.

    More precisly this prints out the generated shell script that would be
    executed by an event line by line.
    """

    def run_script(self, script_path, profilename):
        """Print the script line by line for an event of a given profile. """
        for line in open(script_path, "r").readlines():
            line = line.strip()
            # Skip empty lines
            if not line or line.startswith("#"):
                continue
            log("> " + line)


class EventExecInterpreter(EventInterpreter):
    """This interpreter is used to execute the event scripts of a profile.

    Attributes:
        shell (Process): The shell process used to execute all event callbacks
        queue_out (Queue): Used to push the output of the shell back in realtime
        queue_err (Queue): Used to push exceptions during execution back to
            the main process
        ticks_without_feedback (int): Counter that stores the time in
            milliseconds that the main thread is already waiting for the shell
            script without capturing any output.
        failures (int): Counter that stores how many scripts executed with errors.
    """

    def __init__(self, event_type):
        """Constructor.

        Creates a thread and queues for listening on the shells stdout and
        stderr.
        """
        super().__init__(event_type)
        self.shell = None
        self.ticks_without_feedback = 0
        self.queue_out = Queue()
        self.queue_err = Queue()
        self.failures = 0


    def run_script(self, script_path, profilename):
        """Execute script for the given profile.

        Args:
            script_name (str): The name of the script that was generated
                for an event
            profilename (str): The name of the profile that triggered the
                event
        """
        thread_out = Thread(target=self.listen_for_script_output)
        thread_out.deamon = True

        def stop_execution(msg):
            log_debug(msg)
            log_debug("Terminating shell.")
            self.shell.terminate()
            log_debug("Closing pipes to shell.")
            self.shell.stdout.close()
            log_debug("Waiting for stdout/stderr-listener to terminate...")
            thread_out.join()

        def handle_error():
            # Handle raised exceptions of listener threads
            if not self.queue_err.empty():
                stop_execution("Error detected!")
                raise self.queue_err.get()

        def demote(uid, gid):
            # Changes the current user to original one that started this program
            def result():
                os.setgid(gid)
                os.setuid(uid)
            return result

        # Now the critical part start
        try:
            # Start the shell and start thread to listen to stdout and stderr
            cmd = [const.settings.shell] + const.settings.shell_args.split() + [script_path]
            log_debug(" ".join(cmd))
            self.shell = Popen(
                cmd, stdout=PIPE, stderr=STDOUT,
                preexec_fn=demote(get_uid(), get_gid())
            )
            thread_out.start()

            # Wait for the shell to finish
            self.ticks_without_feedback = 0
            while self.shell.poll() is None:
                self.ticks_without_feedback += 1
                if (self.ticks_without_feedback > const.settings.shell_timeout * 1000 \
                        and const.settings.shell_timeout > 0):
                    stop_execution("Timeout reached!")
                    msg = "Script timed out after "
                    msg += str(const.settings.shell_timeout) + " seconds"
                    raise GenerationError(profilename, msg)
                # Just wait a tick
                time.sleep(.001)
                # Check for exceptions
                handle_error()

            # Shell is done, wait for the last bit of output to arrive
            thread_out.join()
            handle_error()

            # Check if script was successful
            exitcode = self.shell.poll()
            if exitcode:
                raise GenerationError(profilename,
                                      "Script failed with error code: " +
                                      str(exitcode))
        except CustomError as err:
            msg = "The script '" + script_path + "' could not be executed"
            msg += " successfully. Please take a look at it yourself."
            log_error(err._message + "\n" + msg)
            self.failures += 1
        except KeyboardInterrupt:
            msg = "The script '" + script_path + "' was interrupted during"
            msg += " execution. Please take a look at it yourself."
            log_error(err._message + "\n" + msg)
            raise UserAbortion()
        except Exception as err:
            msg = "An unkown error occured during event execution. A "
            msg += "backup of the generated shell script is stored at '"
            msg += script_path + "'. You can try to execute it manually."
            # Convert all exceptions that are not a CustomError in a
            # UnkownError to handle them in the outer pokemon handler
            raise UnkownError(err, msg)

    def listen_for_script_output(self):
        """Runnable of ``thread_out``. Waits for the shell to push something
        to stdout or stderr and prints it. All catched exceptions will be
        stored in ``queue_err`` to handle on the main thread.
        Also resets ``ticks_without_feedback``.
        """
        try:
            last_char = None
            oldbyte = b""
            for byte in iter(lambda: self.shell.stdout.read(1), b""):
                # Reset timeout
                self.ticks_without_feedback = 0
                # Decode byte
                try:
                    if oldbyte:
                        byte = oldbyte + byte
                    byte = byte.decode()
                except UnicodeDecodeError:
                    # We need to use the next byte for decoding as well
                    oldbyte = byte
                    continue
                oldbyte = b""
                # Print byte
                log(byte, end="")
                # Make sure it is printed immediately
                sys.stdout.flush()
                last_char = byte
            # Make sure the script output ends with a new line
            if last_char is not None and last_char != "\n":
                log("")
                sys.stdout.flush()
        except Exception as err:
            self.queue_err.put(err)

    def _op_fin(self, dop):
        """Logs a summary of the executed scripts. If one or more scripts
        failed, it aborts the program"""
        if self.failures:
            msg = str(self.failures) + " script(s) failed to execute"
            raise SystemAbortion(msg)
        if self.shell is not None:
            log_success("Events executed successfully.")


class ExecuteInterpreter(Interpreter):
    """This interpreter actually executes the operations from the DiffLog.

    It can create/delete links in the filesystem and modify the state-file.

    Attributes:
        state (dict): The state-file that will be updated
    """
    def __init__(self, force):
        """Constructor.

        Updates the version number of the state-file.

        Args:
            state (dict): The state-file that will be updated
            force (bool): The value of ``--force``
        """
        super().__init__()
        self.force = force
        self.state = globalstate.current
        self.info_counter = 0
        self.profiles_updated = set()

    def _op_info(self, dop):
        self.info_counter += 1

    def _op_start(self, dop):
        """Logs/Prints out the start of the linking process.

        Args:
            dop (dict): Unused in this implementation
        """
        log_debug("Executing diff operations.")

    def _op_fin(self, dop):
        # Only update the state if the difflog contained at least
        # one operation that is not just displaying information
        if len(self.data) > self.info_counter:
            if const.args.mode != "timewarp":
                if self.profiles_updated:
                    log_debug("Updating modification dates of profiles.")
                for profile in self.profiles_updated:
                    self.state[profile]["updated"] = get_date_time_now()
                self.state.create_snapshot()
                log_success("Profiles updated successfully.")
            else:
                log_success("Timewarp was successful.")

    def _op_untrack_l(self, dop):
        """Removes link from state file

        Args:
            dop (dict): The forget-operation that will be executed
        """
        self.remove_from_state(dop["profile"], dop["symlink"]["path"])

    def _op_update_t(self, dop):
        self.remove_from_state(dop["profile"], dop["symlink1"]["path"])
        self.add_to_state(dop["profile"], dop["symlink2"])

    def _op_track_l(self, dop):
        """Logs/Prints out that a link will be tracked now.

        Args:
            dop (dict): The track-operation that will be logged
        """
        self.add_to_state(dop["profile"], dop["symlink"])

    def _op_restore_l(self, dop):
        if dop["actual_link"]:
            self.remove_symlink(dop["actual_link"]["path"], cleanup=False)
        self.create_symlink(dop["saved_link"], force=True)

    def _op_update_prop(self, dop):
        """Updates the script_path of the onUninstall-script for a profile.

        Args:
            dop (dict): The update-operation that will be executed
        """
        if dop["value"] is None and dop["key"] in self.state[dop["profile"]]:
            del self.state[dop["profile"]][dop["key"]]
        else:
            self.state[dop["profile"]][dop["key"]] = dop["value"]
        self.profiles_updated.add(dop["profile"])

    def _op_add_p(self, dop):
        """Adds a profile entry of the state-file.

        Args:
            dop (dict): The add-operation that will be executed
        """
        new_profile = {}
        new_profile["name"] = dop["profile"]
        new_profile["links"] = []
        new_profile["installed"] = new_profile["updated"] = get_date_time_now()
        if dop["parent"] is not None:
            new_profile["parent"] = dop["parent"]
        self.state[new_profile["name"]] = new_profile

    def _op_remove_p(self, dop):
        """Removes a profile entry of the state-file.

        Args:
            dop (dict): The remove-operation that will be executed
        """
        del self.state[dop["profile"]]

    def _op_update_p(self, dop):
        """Updates a profile entry of the state-file.

        Args:
            dop (dict): The update-operation that will be executed
        """
        self.profiles_updated.add(dop["profile"])

    def _op_add_l(self, dop):
        """Adds a link to the filesystem and adds a link entry of the
        corresponding profile in the state-file.

        Args:
            dop (dict): The add-operation that will be executed
        """
        self.create_symlink(dop["symlink"])
        self.add_to_state(dop["profile"], dop["symlink"])

    def _op_remove_l(self, dop):
        """Removes a link from the filesystem and removes the links entry of
        the corresponding profile in the state-file.

        Args:
            dop (dict): The remove-operation that will be executed
        """
        self.remove_symlink(dop["symlink"]["path"])
        self.remove_from_state(dop["profile"], dop["symlink"]["path"])

    def _op_update_l(self, dop):
        """Updates a link in the filesystem and updates the links entry of
        the corresponding profile in the state-file.

        Args:
            dop (dict): The update-operation that will be executed
        """
        self.remove_symlink(dop["symlink1"]["path"])
        self.remove_from_state(dop["profile"], dop["symlink1"]["path"])
        self.create_symlink(dop["symlink2"])
        self.add_to_state(dop["profile"], dop["symlink2"])

    def add_to_state(self, profilename, linkdescriptor):
        self.state[profilename]["links"].append(linkdescriptor)

    def remove_from_state(self, profilename, linkname):
        """Removes a link entry for a remove_l- or forget_l-operation of
        the corresponding profile in the state-file.

        Args:
            dop (dict): A remove_l- or forget_l-operation
        """
        for link in self.state[profilename]["links"]:
            if link["path"] == linkname:
                self.state[profilename]["links"].remove(link)
                break

    def create_symlink(self, ldescriptor, force=None):
        """Create a symlink in the filesystem.

        Args:
            name (str): The full path of the link that will be created
            target (str): The full path of the file that the link will
                point to
            uid (int): The UID of the owner of the link
            gid (int): The GID of the owner of the link
            permission (int): The permissions of the target
            secure (bool): Wether target should have same owner as name
        Raises:
            UnkownError: The link could not be created
        """
        if force is None:
            force = self.force
        if not os.path.isdir(os.path.dirname(ldescriptor["path"])):
            self._makedirs(ldescriptor["path"])
        self.remove_symlink(ldescriptor["path"], cleanup=False)
        try:
            # Create new link
            if ldescriptor["hard"]:
                os.link(ldescriptor["target"], ldescriptor["path"])
            else:
                os.symlink(ldescriptor["target"], ldescriptor["path"])
            # Set owner and permission
            uid, gid = get_owner_ids(ldescriptor["owner"])
            os.lchown(ldescriptor["path"], uid, gid)
            if ldescriptor["permission"]:
                os.chmod(ldescriptor["path"], int(str(ldescriptor["permission"]), 8))
            # Set owner of symlink
            if ldescriptor["secure"]:
                os.chown(ldescriptor["target"], uid, gid)
            else:
                os.chown(ldescriptor["target"], get_uid(), get_gid())
        except OSError as err:
            raise UnkownError(err, "An unkown error occured when trying to" +
                              " create the link '" + ldescriptor["path"] + "'.")

    def remove_symlink(self, path, cleanup=True):
        """Remove a symlink. If the directory is empty, it removes the
        directory as well. Does this recursively for all parent directories.

        Args:
            path (str): The path to the symlink, that will be removed
        """
        try:
            # Remove existing symlink
            if os.path.lexists(path):
                if os.path.isdir(path):
                    # Overwriting empty dirs is also possible. CheckFileOverwrite
                    # will make sure that the directory is empty
                    os.rmdir(path)
                else:
                    os.unlink(path)
                if cleanup:
                    # go directory tree upwards to remove all empty directories
                    parent = os.path.dirname(path)
                    while not os.listdir(parent):  # while parent dir is empty
                        log_debug("Removing directory '" + parent + "'.")
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
        except OSError as err:
            raise UnkownError(err, "An unkown error occured when trying to" +
                              " remove the link '" + path + "'.")

    @staticmethod
    def _makedirs(filename):
        """Custom ``os.makedirs()`` that keeps the owner of the directory.

        This means that it will create the directory with the same owner as of
        the deepest parent directory that already exists instead of using
        current user as owner. This is needed, because otherwise directories
        won't be accessible by the user, if some links would be created with
        root permissions.

        Args:
            filename (str): The full path of the file that needs its
                directories created
        """
        # First find the deepest directory of the path that exists
        dirname = os.path.dirname(filename)
        while not os.path.isdir(dirname):
            dirname = os.path.dirname(dirname)
        # And remember its owner
        uid, gid = get_owner(dirname)
        top_dir = dirname
        # Then create directories
        dirname = os.path.dirname(filename)
        log_debug("Creating directory '" + dirname + "'.")
        os.makedirs(dirname)
        # And change owner of all created directories to the remembered owner
        while dirname != top_dir:
            os.chown(dirname, uid, gid)
            dirname = os.path.dirname(dirname)


class DetectRootInterpreter(Interpreter):
    """Detects if root permission is needed to perform operations. """

    def _access(self, path):
        """Checks if we have write access for a given path.

        Because the path might not be existent at this point,
        this function goes the full directory tree upwards until it finds
        a directory that we have write accesss to. If it finds one, it
        assumes that we have access to all subdirectories as well.

        Args:
            path (str): The path that will be checked
        Returns:
            bool: True, if we have access to the path
        """
        if not path or path == "/":
            return False
        if not os.path.exists(path):
            return self._access(os.path.dirname(path))
        return os.access(path, os.W_OK)

    def _op_add_l(self, dop):
        """Checks if new links are either created in inaccessible directories
        or will be owned by other users than the current.

        Args:
            dop (dict): The add-operation that will be checked
        """
        name = dop["symlink"]["path"]
        owner = predict_owner(name)
        if not self._access(name):
            self._root_detected(dop, "create links in", os.path.dirname(name))
        elif dop["symlink"]["owner"] != owner:
            self._root_detected(dop, "change owner of", name)

    def _op_remove_l(self, dop):
        """Checks if to be removed links are owned by other users than
        the current.

        Args:
            dop (dict): The remove-operation that will be checked
        """
        if not self._access(dop["symlink"]["path"]):
            self._root_detected(dop, "remove links from",
                                os.path.dirname(dop["symlink"]["path"]))

    def _op_restore_l(self, dop):
        if dop["actual_link"] and not self._access(dop["actual_link"]["path"]):
            self._root_detected(dop, "remove links from",
                                os.path.dirname(dop["actual_link"]["path"]))
        if not self._access(dop["saved_link"]["path"]):
            self._root_detected(dop, "create links in",
                                os.path.dirname(dop["saved_link"]["path"]))


    def _op_update_l(self, dop):
        """Checks if to be updated links are owned by other users than
        the current or will be moved to inaccessible directories.

        Args:
            dop (dict): The update-operation that will be checked
        """
        name = dop["symlink2"]["path"]
        if dop["symlink1"]["owner"] != dop["symlink2"]["owner"]:
            uid, gid = get_owner_ids(dop["symlink2"]["owner"])
            if  uid != get_uid() or gid != get_gid():
                self._root_detected(dop, "change the owner of", name)
        if dop["symlink1"]["path"] != dop["symlink2"]["path"]:
            if not self._access(dop["symlink2"]["path"]):
                self._root_detected(dop, "create links in",
                                    os.path.dirname(name))
            if not self._access(dop["symlink1"]["path"]):
                self._root_detected(dop, "remove links from",
                                    os.path.dirname(name))
        if dop["symlink1"]["target"] != dop["symlink2"]["target"]:
            if not self._access(dop["symlink2"]["path"]):
                self._root_detected(dop, "change target of", name)
        if dop["symlink1"]["secure"] != dop["symlink2"]["secure"]:
            if not self._access(dop["symlink2"]["path"]):
                self._root_detected(dop,
                                    "change owner of",
                                    dop["symlink2"]["target"])

    @abstractmethod
    def _root_detected(self, dop, description, affected_file):
        """This method is called when requirement of root permission
        is detected.

        Args:
            dop (dict): The operation that requires root permission
            description (str): A description of what the operation does that
                will require root permission
            affected_file (str): The file that the description refers to
        """
        raise NotImplementedError


class SkipRootInterpreter(DetectRootInterpreter):
    """Skips all operations that would require root permission.

    Attributes:
        skipped (list): A list of all operations that will be skipped
        skipped_reasons (list): A list of tuples that counts how often a
            description occured
    """

    def __init__(self):
        super().__init__()
        self.skip = []
        self.skipped_reasons = {}

    def _op_start(self, dop):
        log_debug("Removing operations that require root.")

    def _root_detected(self, dop, description, affected_file):
        """Stores which operations needs to be skipped.

        Args:
            dop (dict): The operation that will be skipped
            description (str): A description of what the operation does that
                will require root permission
            affected_file (str): Used to determine if description refers to
                a file or a directory
        """
        self.skip.append(dop)
        if os.path.isdir(affected_file):
            description += " directories"
        else:
            description += " files"
        if description not in self.skipped_reasons:
            self.skipped_reasons[description] = 1
        else:
            self.skipped_reasons[description] += 1

    def _op_fin(self, dop):
        """Remove all operations from difflog that are collected in
        ``self.skip``.

        Args:
            dop (dict): Unused in this implementation
        """
        # Remove all operations from self.skip
        new_data = []
        for operation in self.data:
            if operation in self.skip:
                self.skip.remove(operation)
            else:
                new_data.append(operation)
        self.data.clear()
        for operation in new_data:
            self.data.append(operation)
        # Print out summary of what we skipped
        for reason, count in self.skipped_reasons.items():
            if count == 1:
                log_warning("Skipping 1 operation that would " +
                            "require root permission to " + reason + ".")
            else:
                log_warning("Skipping " + str(count) + " operations that " +
                            "would require root permission to " + reason + ".")


class RootNeededInterpreter(DetectRootInterpreter):
    """Checks if root permission are required to perform all operations.
    Prints out all such operations.

    Attributes:
         content (list): A list of tuples with (dop, description, affected_file)
            that stores which operations require root permission, which file
            or directory they affect and a description of what the operation
            would exactly require root permission for
    """

    def __init__(self):
        super().__init__()
        self.logged = []

    def _root_detected(self, dop, description, affected_file):
        """Logs and prints out the operation that needs root permission.

        Args:
            dop (dict): Unused in this implementation
            description (str): A description of what the operation does that
                will require root permission
            affected_file (str): The file that the description refers to
        """
        if affected_file not in self.logged:
            self.logged.append(affected_file)
            log_warning("Root permission required to " + description +
                        " '" + affected_file + "'.")


class GainRootInterpreter(RootNeededInterpreter):
    """If root permission is needed to perform the operations,
    this interpreter restarts the process with "sudo".
    """
    def _op_fin(self, dop):
        """Replace the process if root permission is needed with the same call
        of uberdot, but prepend it with "sudo".

        Args:
            dop (dict): Unused in this implementation
        """
        if self.logged:
            if const.settings.askroot:
                pickle_path = abspath("uberdot.pickle")
                pickle.dump((const, self.data), open(pickle_path))
                args = [sys.executable, "exec", pickle_path]
                call_msg = "'sudo " + " ".join(args) + "'"
                log_debug("Replacing process with " + call_msg + ".")
                os.execvp('sudo', args)
            else:
                raise UserError("You need to restart uberdot using 'sudo'" +
                                " or using the '--skiproot' option.")
