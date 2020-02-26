"""This module implements the Difference-Solvers (at the moment there is only
the standart DiffSolver) and their resulting data structure DiffLog.

.. autosummary::
    :nosignatures:

    DiffLog
    DiffSolver
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


import copy
import os
from abc import abstractmethod
from uberdot import constants as const
from uberdot.errors import FatalError
from uberdot.installedfile import AutoExpandDict
from uberdot.interpreters import Interpreter
from uberdot.utils import get_date_time_now
from uberdot.utils import import_profile_class
from uberdot.utils import get_owner
from uberdot.utils import get_permission
from uberdot.utils import log_debug
from uberdot.utils import log_warning
from uberdot.utils import normpath


def links_similar(sym1, sym2):
    return normpath(sym1["from"]) == normpath(sym2["from"]) or \
           normpath(sym1["to"]) == normpath(sym2["to"])

def links_equal(link1, link2):
    print("LinkDescriptors: ", link1, link2)
    return normpath(link1["from"]) == normpath(link2["from"]) and \
           normpath(link1["to"]) == normpath(link2["to"]) and \
           link1["uid"] == link2["uid"] and \
           link1["gid"] == link2["gid"] and \
           link1["permission"] == link2["permission"] and \
           link1["secure"] == link2["secure"]

def link_exists(link):
    file = link["from"]
    props = {}
    props["from"] = file
    props["to"] = os.readlink(file)
    props["uid"], props["gid"] = get_owner(file)
    props["permission"] = get_permission(file)
    props["secure"] = get_permission(file) == get_permission(os.readlink(file))
    props["date"] = os.path.getmtime(file)
    return links_equal(link, props)


class DiffLog():
    """This class stores the operations that were determined by a
    Difference-Solver. Furthermore it provides helpers to create such
    operations and a function that allows multiple interpreters to interprete
    the operations at the same time.

    Attributes:
        data (list): Used to store the operations
    """
    def __init__(self):
        """Constructor"""
        self.data = []

    def show_info(self, profilename, message):
        """Create an info operation.

        Info operations can be used to print out profile information to the
        user. At the moment this is only evaluated by the
        :class:`~interpreters.PrintInterpreter` to print out a string like::

            [profilename]: message

        Args:
            profilename (str): The name of the profile that prints the
                information
            message (str): The message to be printed
        """
        self.__append_data("info", profilename, message=message)

    def add_profile(self, profilename, parentname=None):
        """Create an add-profile operation.

        Add-profile operations indicate that a new profile will be
        added/installed. This will be - for example - evalutated by the
        :class:`~interpreters.ExecuteInterpreter` to create a new empty entry
        in the installed-file.

        Args:
            profilename (str): The name of the new profile
            parentname (str): The name of the parent of the new profile. If
                ``None`` it will be treated as a root profile
        """
        self.__append_data("add_p", profilename, parent=parentname)

    def update_profile(self, profilename):
        """Create an update-profile operation.

        Update-profile operations indicate that a certain profile will be
        updated. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to update the changed-date of
        a profile in the installed file.

        Args:
            profilename (str): The name of the to be updated profile
        """
        self.__append_data("update_p", profilename)

    def update_parent(self, profilename, parentname):
        """Create an update-parent operation.

        Update-parent operations indicate that a certain profile will change
        its parent.

        Args:
            profilename (str): The name of the to be updated profile
            parentname (str): The name of the new parent of the profile. If
                ``None`` it will be a root profile from now on.
        """
        self.__append_data("update_p", profilename, parent=parentname)

    def remove_profile(self, profilename):
        """Create a remove-profile operation.

        Remove-profile operations indicate that a certain profile will be
        removed/uninstalled. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the profile in the
        installed file.

        Args:
            profilename (str): The name of the to be removed profile
        """
        self.__append_data("remove_p", profilename)

    def add_link(self, symlink, profilename):
        """Create an add-link operation.

        Add-link operations indicate that a new link needs to be created.
        This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to create the link in the
        filesystem and create an entry in the installed file.

        Args:
            symlink (dict): A dictionary that describes the symbolic link that
                needs to be created
            profilename (str): The name of profile that the link belongs to
        """
        symlink["date"] = get_date_time_now()
        self.__append_data("add_l", profilename, symlink=symlink)

    def remove_link(self, symlink_name, profilename):
        """Create a remove-link operation.

        Remove-link operations indicate that a certain link needs to be
        removed. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the link from the
        filesystem and the installed file.

        Args:
            symlink_name (str): The absolute path to the symbolic link
            profilename (str): The profile that the link is removed from
        """
        self.__append_data("remove_l", profilename, symlink_name=symlink_name)

    def update_link(self, installed_symlink, new_symlink, profilename):
        """Create an update-link operation.

        Update-link operations indicate that a certain link needs to be
        replaced by a new link. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the old link from
        the filesystem, create the new link in the filesystem and update the
        entry of the old link in the installed-file.

        Args:
            installed_symlink (dict): A dictionary that describes the symbolic
                link that needs to be replaced
            new_symlink (dict): A dictionary that describes the symbolic
                link that will replace the old link
        """
        new_symlink["date"] = get_date_time_now()
        self.__append_data("update_l", profilename,
                           symlink1=installed_symlink,
                           symlink2=new_symlink)

    def update_property(self, key, value, profilename):
        """Create an update-script operation.

        Update-script operations indicate that the onUninstall-script needs to
        be updated by a new path. This will be evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to update the entry of the
        old script in the installed-file.

        Args:
            enabled (bool): True, if script shall be executed
            profilename (str): The name of the profile that will be updated
        """
        self.__append_data("update_prop", profilename, key=key, value=value)

    def track_link(self, symlink, profilename):
        symlink["date"] = os.path.getmtime(symlink["from"])
        self.__append_data("track_l", profilename, symlink=symlink)

    def untrack_link(self, symlink_name, profilename):
        self.__append_data("untrack_l", profilename, symlink_name=symlink_name)

    def __append_data(self, operation, profilename, **kwargs):
        """Appends a new operation to :attr:`self.data<DiffLog.data>`.

        Args:
            operation (str): Name of the operation
            profilename (str): Name of the profile that is associated with the
                operation
            **kwargs (dict): All further key/value pairs of the operation
        """
        self.data.append(
            {"operation": operation, "profile": profilename, **kwargs}
        )

    def run_interpreter(self, *interpreters):
        """Run a list of :mod:`interpreters` for all operations.

        This function iterates over all operations and evaluates them by
        feeding them into the given interpreters. Furthermore it initializes
        the interpreters and feeds them additional "start" and "fin"
        operations.

        Args:
            interpreters (Interpreter): A list of interpreters that will
                interpret the operations
        """
        # Initialize interpreters
        for interpreter in interpreters:
            interpreter.set_difflog_data(self.data)
        # Send a "start" operation to indicate that operations will follow
        for interpreter in interpreters:
            interpreter.call_operation({"operation": "start"})
        # Run interpreters for every operation
        for operation in self.data:
            for interpreter in interpreters:
                interpreter.call_operation(operation)
        # And send a "fin" operation when we are finished
        for interpreter in interpreters:
            interpreter.call_operation({"operation": "fin"})


class DiffSolver():
    """This is the abstract base class for difference solvers. Difference
    solver take two "different states" of the filesystem (e.g. one state
    could be an installed-file and another one a result of executed profiles)
    and create a :class:`DiffLog` that holds all operations that are needed to
    transfer from the fist state to the second.

    Attributes:
        difflog (Difflog): The DiffLog that will be used to store all
            calculated operations
    """

    def __init__(self):
        """ Constructor."""
        self.difflog = None

    def solve(self, difflog=None):
        """Start solving differences.

        Args:
            difflog (DiffLog): A DiffLog that will be used to store (append)
                all operations instead of the internal DiffLog
        returns:
            DiffLog: the resulting DiffLog
        """
        if difflog is None:
            self.difflog = DiffLog()
        else:
            self.difflog = difflog
        self._generate_operations()
        return self.difflog

    @abstractmethod
    def _generate_operations(self):
        """Calculate the operations needed to solve the differences and append
        them to ``self.difflog``. Needs to be implemented by subclasses.
        """
        raise NotImplementedError


class StateFilesystemDiffSolver(DiffSolver):
    def __init__(self, state, users=[const.user], action=None):
        super().__init__()
        self.state = state
        self.users = users
        if action is not None
            self.action = action
        else:
            self.action = const.action

    def _generate_operations(self):
        for user in self.users:
            if user in self.state.get_users():
                for profile in self.state.get_user_profiles(user):
                    self.__generate_profile_fix(profile)

    def __generate_profile_fix(self, profile):
        def fix_link(self, fix_description, remove=None):
            if self.action:
                # TODO: make this fail save
                # TODO store last fix selection in case of error
                selection = self.action
            else:
                selection = input(fix_description + " (s/r/t/u/?) ").lower()
            if selection == "s":
                return
            elif selection == "r":
                # TODO operation needed that restores a link
                pass
            elif selection == "t":
                # TODO operation needed that restores a link
                pass
            elif selection == "u":
                # Remove link from installed file
                self.difflog.untrack_l(profile, link)
            else:
                if selection == "?":
                    log("(s)kip / (r)estore link / (t)ake over / (u)ntrack link")
                else:
                    log("Unkown option")
                fix_link(fix_description, remove)
        for link in profile["links"]:
            # Check if link still exists
            if not os.path.exists(link["name"]):
                # Check if another symlink exists that has same target
                for root, name in safe_walk(os.path.dirname(link["name"])):
                    file = os.path.join(root, name)
                    if os.path.realpath(file) == link["target"]:
                        msg = "Link '" + link["name"] + "' was renamed '"
                        msg += " to '" + file + "'."
                        fix_link(msg, file)
                        break
                # No other symlink exists, file must have been removed
                fix_link("Link '" + link["name"] + "' was removed.")
            # Check if link still points to same target
            elif os.path.realpath(link["name"]) != link["target"]:
                msg = "Link '" + link["name"] + "' now points to '"
                msg += link["target"] + "'."
                fix_link(msg, link["name"])
            # TODO: check if target still exists (link broken)
            # TODO: Check for props


class UninstallDiffSolver(DiffSolver):
    """This difference solver takes the current installed file and a list of
    profile names. It is used to calculate all operations needed to uninstall
    the given profiles.

    Attributes:
        installed (dict): The installed-file that is used for solving
        profile_names (list): A list of profile names that will be uninstalled
    """
    def __init__(self, installed, profile_names):
        """ Constructor.

        Args:
            installed (dict): The installed-file that is used for solving
            profile_names (list): A list of profile names that will be
                uninstalled
        """
        super().__init__()
        self.installed = installed
        self.profile_names = profile_names

    def _generate_operations(self):
        """Generates operations to remove all installed profiles of
        ``profilelist``.

        Skips profiles that are not installed.
        """
        for profilename in self.profile_names:
            if profilename in self.installed:
                self.__generate_profile_unlink(profilename)
            else:
                log_warning("The profile " + profilename +
                            " is not installed at the moment. Skipping...")

    def __generate_profile_unlink(self, profile_name):
        """Generate operations to remove a single installed profile.

        Appends to :class:`DiffLog` that we want to remove a profile,
        all it's subprofiles and all their links.

        Args:
            profile_name (str): Name of the profile that will be removed
        """
        if profile_name in const.ignore:
            log_debug("'" + profile_name + "' is in ignore list. Skipping...")
            return
        # Recursive call for all subprofiles
        subprofiles = []
        for installed_name, installed_dict in self.installed.items():
            if ("parent" in installed_dict and
                    installed_dict["parent"] == profile_name):
                subprofiles.append(installed_name)
        self._generate_operations(subprofiles)
        # We are removing all symlinks of this profile before we
        # remove the profile from the installed file
        installed_links = copy.deepcopy(self.installed[profile_name]["links"])
        for installed_link in installed_links:
            self.difflog.remove_link(installed_link["from"], profile_name)
        self.difflog.remove_profile(profile_name)


# class HistoryDiffSolver(DiffSolver):


class UpdateDiffSolver(DiffSolver):
    """This solver determines the differences between an installed-file
    and a list of profiles.

    Attributes:
        installed (dict): The installed-file that is used for solving
        profile_results (dict): The result of the executed profiles
        parent(str): The name of the parent that all profiles will change
            its parent to (only set if ``--parent`` was specified)
    """
    def __init__(self, installed, profile_results, parent):
        """ Constructor.

        Args:
            installed (dict): The installed-file that is used for solving
            profile_results (list): A list of the result of the executed
                profiles
            parent (str): The value of the cli argument --parent
        """
        super().__init__()
        self.installed = installed
        self.profile_results = profile_results
        self.parent = parent

    def _generate_operations(self):
        """Generates operations to update all profiles.

        This function resolves each root profile with their subprofiles
        separately.
        """
        allpnames = []

        def add_profilenames(profile):
            """Recursively add all names of subprofiles to allpnames"""
            allpnames.append(profile["name"])
            for prof in profile["profiles"]:
                add_profilenames(prof)

        for profile in self.profile_results:
            add_profilenames(profile)
        for profile in self.profile_results:
            # Generate difflog from diff between links and installed
            self.__generate_profile_link(profile, allpnames, self.parent)

    def __generate_profile_link(self, profile_dict, all_profilenames,
                                parent_name):
        """Generate operations for resolving the differences between a single
        profile and the installed ones and appends the corresponding operations
        to the DiffLog for those differences. Calls itself recursively for all
        subprofiles.

        Args:
            profile_dict (dict): The result of an executed profile that will be
                compared against the installed-file
            all_profilenames (list): A list with all profile names (including
                all sub- and root-profiles)
            parent_name (str): The name of the profiles (new) parent. If
                parent_name is ``None``, the profile is treated as a root
                profile
        """

        profile_new = False
        profile_changed = False

        # Load the links from the InstalledLog
        profile_name = profile_dict["name"]
        if profile_name in const.ignore:
            log_debug("'" + profile_name + "' is in ignore list. Skipping...")
            return
        installed_profile = None
        if profile_name in self.installed:
            installed_profile = self.installed[profile_name]
            installed_links = copy.deepcopy(installed_profile["links"])
        else:
            installed_links = []
            # The profile wasn't installed
            self.difflog.add_profile(profile_name, parent_name)
            profile_new = True
        # And from the new profile
        new_links = copy.deepcopy(profile_dict["links"])

        # Now we can compare installed_dict and profile_dict and write
        # the difflog that resolves these differences
        # To do so we actually compare installed_links with new_links
        # and check which links
        #   - didn't changed (must be the same in both)
        #   - are removed (occure only in installed_links)
        #   - are updated (two links that differ, but name or target are same)
        #   - are added (occure only in new_links)
        # Whenever we find a link to be unchanged/removed/etc. we will remove
        # it from new_links and installed_links, so in the end both lists
        # need to be empty.

        # TODO: check if new/removed/updated links already exist like they are
        # supposed to. if so just add/remove/update them in the installed file
        # (new operations needed)
        # Maybe could be done in the CheckLinkExists interpreter

        # Check all unchanged
        count = 0
        for installed_link in installed_links[:]:
            for new_link in new_links[:]:
                if links_equal(installed_link, new_link):
                    # Link in new profile is the same as a installed one,
                    # so we do nothing to the difflog
                    installed_links.remove(installed_link)
                    new_links.remove(new_link)
                    count += 1
                    break
        if count > 0:
            msg = str(count)
            msg += " links will be left untouched, no changes here..."
            self.difflog.show_info(profile_name, msg)

        # Check all removed
        for installed_link in installed_links[:]:
            remove = True
            for new_link in new_links[:]:
                if links_similar(installed_link, new_link):
                    remove = False
                    break
            if remove:
                # Installed link is not similiar to any new link, so create
                # a remove operation in the difflog
                profile_changed = True
                self.difflog.remove_link(installed_link["from"], profile_name)
                installed_links.remove(installed_link)

        # Check all changed and added links
        for new_link in new_links[:]:
            add = True
            for installed_link in installed_links[:]:
                if links_similar(installed_link, new_link):
                    # new_link has same name or target, so we need to create
                    # an update operation in the difflog
                    profile_changed = True
                    self.difflog.update_link(installed_link, new_link,
                                             profile_name)
                    installed_links.remove(installed_link)
                    new_links.remove(new_link)
                    add = False
                    break
            if add:
                # There was no similar installed link, so we need to create an
                # add operation in the difflog
                profile_changed = True
                self.difflog.add_link(new_link, profile_name)
                new_links.remove(new_link)

        # We removed every symlink from new_links and installed_links when
        # we found the correct operation for them. If they aren't empty now,
        # something obviously went wrong.
        if new_links or installed_links:
            raise FatalError("Couldn't resolve differences between the " +
                             "installed and the new version of profile " +
                             profile_name)

        # Remove all installed subprofiles that doesnt occur in profile anymore
        if installed_profile is not None:
            installed_subprofiles = set()
            profiles_subprofiles = set()
            # First get all subprofiles that were installed
            for installed_name, installed_dict in self.installed.items():
                if "parent" in installed_dict:
                    if installed_dict["parent"] == profile_name:
                        installed_subprofiles.add(installed_name)
            # Then get all subprofiles that shall be installed
            if "profiles" in profile_dict:
                for subprofile in profile_dict["profiles"]:
                    profiles_subprofiles.add(subprofile["name"])
            # With those we generate the list of subprofiles that need to be
            # uninstalled
            old_subprofiles = [item for item in installed_subprofiles
                               if item not in profiles_subprofiles]
            # But don't uninstall old subprofiles that only changed their
            # parent
            for i in range(len(old_subprofiles)-1, -1, -1):
                if old_subprofiles[i] in all_profilenames:
                    old_subprofiles.pop(i)
            # We can use another DiffSolver to create all the operations needed
            # to uninstall all the old profiles and all their links
            dfs = UninstallDiffSolver(self.installed, old_subprofiles)
            dfs.solve(self.difflog)

        # If something in the profile changed we need to update
        # its modification date and maybe its parent reference too
        if installed_profile is not None:
            # Check if parent changed
            parent_changed = False
            if "parent" in installed_profile:
                if parent_name != installed_profile["parent"]:
                    parent_changed = True
            elif parent_name is not None:
                parent_changed = True
            # Update profile
            if parent_changed:
                self.difflog.update_parent(profile_name, parent_name)
            elif profile_changed and not profile_new:
                self.difflog.update_profile(profile_name)

        # Update old scripts for uninstall
        event = "beforeUninstall"
        self.difflog.update_property(event, profile_dict[event], profile_name)
        event = "afterUninstall"
        self.difflog.update_property(event, profile_dict[event], profile_name)

        # Recursive call for all subprofiles
        if "profiles" in profile_dict:
            for subprofile in profile_dict["profiles"]:
                self.__generate_profile_link(subprofile,
                                             all_profilenames,
                                             profile_name)
