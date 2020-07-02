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
from uberdot.state import AutoExpandDict
from uberdot.state import GlobalState
from uberdot.interpreters import Interpreter
from uberdot.utils import *

const = Const()
globalstate = GlobalState()

class DiffLog():
    """This class stores the operations that were determined by a
    Difference-Solver. Furthermore it provides helpers to create such
    operations and a function that allows multiple interpreters to interprete
    the operations at the same time.

    The following operations are supported:
        op_start: Called before all other operations
        op_fin: Called after all other operations
        op_info: Log/print some information
        op_add_p: Adds a new profile
        op_update_p: Updates an existing profile
        op_remove_p: Removes an existing profile
        op_update_prop: Update a property of a profile
        op_add_l: Create new link and track it
        op_update_l: Updates an existing link
        op_remove_l: Removes an existing link and stops tracking
        op_track_l: Tracks existing link
        op_untrack_l: Don't track an existing link anymore
        op_restore_l: Restore (non-)existing link

    Attributes:
        data (list): Used to store the operations
    """
    def __init__(self):
        """Constructor"""
        self.data = []

    def __len__(self):
        return len(self.data)

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

    def add_profile(self, profilename, event_before, event_after, parentname=None):
        """Create an add-profile operation.

        Add-profile operations indicate that a new profile will be
        added/installed. This will be - for example - evalutated by the
        :class:`~interpreters.ExecuteInterpreter` to create a new empty entry
        in the state file.

        Args:
            profilename (str): The name of the new profile
            parentname (str): The name of the parent of the new profile. If
                ``None`` it will be treated as a root profile
        """
        self.__append_data("add_p", profilename, before=event_before, after=event_after, parent=parentname)

    def update_profile(self, profilename, event_before, event_after):
        """Create an update-profile operation.

        Update-profile operations indicate that a certain profile will be
        updated. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to update the changed-date of
        a profile in the state file.

        Args:
            profilename (str): The name of the to be updated profile
        """
        self.__append_data("update_p", profilename, before=event_before, after=event_after)

    def remove_profile(self, profilename, event_before, event_after):
        """Create a remove-profile operation.

        Remove-profile operations indicate that a certain profile will be
        removed/uninstalled. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the profile in the
        state file.

        Args:
            profilename (str): The name of the to be removed profile
        """
        self.__append_data("remove_p", profilename, before=event_before, after=event_after)

    def restore_link(self, profilename, saved_link, actual_link):
        self.__append_data("restore_l",
                           profilename,
                           saved_link=saved_link,
                           actual_link=actual_link)

    def add_link(self, profilename, symlink):
        """Create an add-link operation.

        Add-link operations indicate that a new link needs to be created.
        This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to create the link in the
        filesystem and create an entry in the state file.

        Args:
            symlink (dict): A dictionary that describes the symbolic link that
                needs to be created
            profilename (str): The name of profile that the link belongs to
        """
        symlink["date"] = get_date_time_now()
        self.__append_data("add_l", profilename, symlink=symlink)

    def remove_link(self, profilename, symlink):
        """Create a remove-link operation.

        Remove-link operations indicate that a certain link needs to be
        removed. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the link from the
        filesystem and the state file.

        Args:
            symlink_name (str): The absolute path to the symbolic link
            profilename (str): The profile that the link is removed from
        """
        if similar_link_exists(symlink):
            self.__append_data("remove_l", profilename, symlink=symlink)
        else:
            self.untrack_link(profilename, symlink)

    def update_link(self, profilename, installed_symlink, new_symlink):
        """Create an update-link operation.

        Update-link operations indicate that a certain link needs to be
        replaced by a new link. This will be - for example - evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to remove the old link from
        the filesystem, create the new link in the filesystem and update the
        entry of the old link in the state file.

        Args:
            installed_symlink (dict): A dictionary that describes the symbolic
                link that needs to be replaced
            new_symlink (dict): A dictionary that describes the symbolic
                link that will replace the old link
        """
        # There are multiple cases when updating a symlink
        # 1. The installed link was already manually removed
        if not os.path.lexists(installed_symlink["from"]):
            self.untrack_link(profilename, installed_symlink)
            # 1a. The new link already exists
            if link_exists(new_symlink):
                self.track_link(profilename, new_symlink)
            # 1b. The new link needs to be created
            else:
                self.add_link(profilename, new_symlink)
        # 2. A similar installed link exists but the new link already exists
        elif link_exists(new_symlink):
            if installed_symlink["from"] != new_symlink["from"]:
                self.remove_link(profilename, installed_symlink)
            self.track_link(profilename, new_symlink)
        # 3. A similar installed link exists and new link does not exist
        else:
            new_symlink["date"] = get_date_time_now()
            self.__append_data("update_l", profilename,
                               symlink1=installed_symlink,
                               symlink2=new_symlink)

    def update_property(self, profilename, key, value):
        """Create an update-script operation.

        Update-script operations indicate that the onUninstall-script needs to
        be updated by a new path. This will be evaluated by the
        :class:`~interpreters.ExecuteInterpreter` to update the entry of the
        old script in the state file.

        Args:
            enabled (bool): True, if script shall be executed
            profilename (str): The name of the profile that will be updated
        """
        self.__append_data("update_prop", profilename, key=key, value=value)

    def track_link(self, profilename, symlink):
        self.__append_data("track_l", profilename, symlink=symlink)

    def untrack_link(self, profilename, symlink):
        self.__append_data("untrack_l", profilename, symlink=symlink)

    def update_tracked(self, profilename, old_symlink, new_symlink):
        self.__append_data("update_t", profilename, symlink1=old_symlink, symlink2=new_symlink)

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
    could be an state file and another one a result of executed profiles)
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
    def __init__(self, action=""):
        super().__init__()
        self.action = action

    def _generate_operations(self):
        # Go through profiles and generate operations for each of them
        for profile in globalstate.current.values():
            if profile["name"] in const.args.exclude:
                continue
            self.__generate_profile_fix(profile)

    def __generate_profile_fix(self, profile):
        for link in profile["links"]:
            if link.exists():
                # If the link exists like this, there is no difference
                continue
            # So lets figure out what's different about the installed link
            profilename = profile["name"]
            # Check if link still exists
            if not os.path.exists(link["from"]):
                # Check if another symlink exists that has same target
                dirname = os.path.dirname(link["from"])
                renamed = False
                if os.path.exists(dirname):
                    for file in listfiles(dirname):
                        if readlink(file) == link["to"]:
                            msg = "Link '" + link["from"] + "' was renamed"
                            msg += " to '" + file + "'."
                            self.fix_link(
                                msg, profilename, link,
                                get_linkdescriptor_from_file(file)
                            )
                            renamed = True
                            break
                if not renamed:
                    # No other symlink exists, file must have been removed
                    self.fix_link(
                        "Link '" + link["from"] + "' was removed.",
                        profilename, link, {}
                    )
            # Check if link still points to same target
            elif readlink(link["from"]) != link["to"]:
                msg = "Link '" + link["from"] + "' now points to '"
                msg += readlink(link["from"]) + "'."
                self.fix_link(
                    msg, profilename, link,
                    get_linkdescriptor_from_file(link["from"])
                )
            # Another property changed
            else:
                actual_link = get_linkdescriptor_from_file(link["from"])
                msg = "Properties of link '" + link["from"]
                msg += "' changed:" + "\n"
                if actual_link["owner"] != link["owner"]:
                    msg += "  owner: " + link["owner"] + " -> "
                    msg += actual_link["owner"] + "\n"
                if actual_link["permission"] != link["permission"]:
                    msg += "  permission: " + str(link["permission"]) + " -> "
                    msg += str(actual_link["permission"]) + "\n"
                if actual_link["secure"] != link["secure"]:
                    msg += "  secure: " + str(link["secure"]) + " -> "
                    msg += str(actual_link["secure"]) + "\n"
                self.fix_link(msg, profilename, link, actual_link)

    def fix_link(self, fix_description, profilename, saved_link, actual_link):
        # Setup selection for how to solve the difference
        selection = self.action if self.action != "d" else ""
        if not selection:
            print(fix_description)
            selection = user_choice(
                ("S", "Skip"), ("R", "Restore link"),
                ("T", "Take over"), ("U", "Untrack link")
            )
        # Solve according to the selection
        if selection == "s":
            return
        elif selection == "r":
            self.difflog.restore_link(profilename, saved_link, actual_link)
        elif selection == "t":
            if actual_link:
                self.difflog.update_tracked(profilename, saved_link, actual_link)
            else:
                self.difflog.untrack_link(profilename, saved_link)
        elif selection == "u":
            self.difflog.untrack_link(profilename, saved_link)


class StateFilesystemDiffFinder(StateFilesystemDiffSolver):
    def __init__(self):
        super().__init__("t")

    def fix_link(self, fix_description, profilename, saved_link, actual_link):
        self.difflog.show_info(profilename, fix_description)


class RemoveProfileDiffSolver(DiffSolver):
    #### DANGEROUS ####
    def __init__(self, state, profile_names):
        """ Constructor.

        Args:
            state (State): The state file that is used for solving
            profile_names (list): A list of profile names that will be
                uninstalled
        """
        super().__init__()
        self.state = state
        self.profile_names = profile_names

    def _generate_operations(self, profilelist=None):
        """Generates operations to remove all installed profiles of
        ``profilelist``.

        Skips profiles that are not installed.
        """
        if profilelist is None:
            profilelist = self.profile_names
        for profilename in profilelist:
            if profilename in self.state:
                self.generate_profile_remove(profilename)
            else:
                log_warning("The profile " + profilename +
                            " is not installed at the moment. Skipping...")

    def generate_profile_remove(self, profile_name):
        # We are removing all symlinks of this profile before we
        # remove the profile from the state file
        for installed_link in self.state[profile_name]["links"]:
            self.difflog.remove_link(profile_name, installed_link)
        # Remove the profile itself
        self.difflog.remove_profile(profile_name,
                                    self.state[profile_name]["beforeUninstall"],
                                    self.state[profile_name]["afterUninstall"])


class UninstallDiffSolver(RemoveProfileDiffSolver):
    """This difference solver takes the current state file and a list of
    profile names. It is used to calculate all operations needed to uninstall
    the given profiles and all subprofiles.

    Attributes:
        state (State): The state file that is used for solving
        profile_names (list): A list of profile names that will be uninstalled
    """
    def __init__(self, profilenames):
        super().__init__(globalstate.current, profilenames)

    def generate_profile_remove(self, profile_name):
        """Generate operations to remove a single installed profile.

        Appends to :class:`DiffLog` that we want to remove a profile,
        all it's subprofiles and all their links.

        Args:
            profile_name (str): Name of the profile that will be removed
        """
        if profile_name in const.args.exclude:
            log_debug("'" + profile_name + "' is in exclude list. Skipping...")
            # Even though we skip it, we need to make sure that the profile is
            # no longer a subprofile, because at this point profile_name is
            # either a root profile or we will definitely generate the remove
            # operations for its parent
            if "parent" in self.state[profile_name]:
                self.difflog.update_property(profile_name, "parent", None)
            return
        # Recursive call for all subprofiles
        subprofiles = []
        for installed_name, installed_dict in self.state.items():
            if ("parent" in installed_dict and
                    installed_dict["parent"] == profile_name):
                subprofiles.append(installed_name)
        self._generate_operations(subprofiles)
        super().generate_profile_remove(profile_name)


class LinkListDiffSolver(DiffSolver):
    def solve_link_list(self, profile_name, installed_links, new_links):
        installed_links = installed_links.copy()
        new_links = new_links.copy()
        profile_changed = False
        # We compare installed_links with new_links and check which links
        #   - didn't changed (must be the same in both)
        #   - are removed (occure only in installed_links)
        #   - are added (occure only in new_links)
        #   - are updated (two links that differ, but name or target are same)
        # Whenever we find a link to be unchanged/removed/etc. we will remove
        # it from new_links and installed_links, so in the end both lists
        # need to be empty.

        # Check all unchanged
        count = 0
        for installed_link in installed_links[:]:
            for new_link in new_links[:]:
                if installed_link == new_link:
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
            for new_link in new_links[:]:
                if installed_link.issimilar(new_link):
                    break
            else:
                # Installed link is not similiar to any new link, so it
                # needs to be removed
                profile_changed = True
                self.difflog.remove_link(profile_name, installed_link)
                installed_links.remove(installed_link)

        # Check all changed and added links
        for new_link in new_links[:]:
            for installed_link in installed_links[:]:
                if installed_link.issimilar(new_link):
                    # new_link has same name or target, so we need to create
                    # an update operation in the difflog
                    profile_changed = True
                    # Check if it was already updated in the filesystem
                    self.difflog.update_link(profile_name, installed_link,
                                             new_link)
                    installed_links.remove(installed_link)
                    new_links.remove(new_link)
                    break
            else:
                # There was no similar installed link, so we need to create an
                # add operation in the difflog
                profile_changed = True
                if new_link.exist():
                    self.difflog.track_link(profile_name, new_link)
                else:
                    self.difflog.add_link(profile_name, new_link)
                new_links.remove(new_link)

        # We removed every symlink from new_links and installed_links when
        # we found the correct operation for them. If they aren't empty now,
        # something obviously went wrong.
        if new_links or installed_links:
            raise FatalError("Couldn't resolve differences between the " +
                             "installed and the new version of profile " +
                             profile_name)

        return profile_changed


class StateDiffSolver(LinkListDiffSolver):
    def __init__(self, old_state, new_state):
        super().__init__()
        self.old_state = old_state.copy()
        self.new_state = new_state.copy()

    def _generate_operations(self):
        if const.args.include:
            self.solve_included()
        else:
            self.solve_all()

    def _remove_old_profiles(self, profiles):
        old_profiles = []
        for profile in profiles:
            if profile in const.args.exclude:
                log_debug("'" + profile + "' is in exclude list. Skipping...")
                continue
            if profile not in self.new_state:
                old_profiles.append(profile)
        RemoveProfileDiffSolver(self.old_state, old_profiles).solve(self.difflog)
        return old_profiles

    def _update_profiles(self, profiles):
        for profile in profiles:
            if profile in const.args.exclude:
                log_debug("'" + profile + "' is in exclude list. Skipping...")
                continue
            for prop in self.old_state[profile]:
                if prop == "links":
                    continue
                if self.old_state[profile][prop] != self.new_state[profile][prop]:
                    self.difflog.update_property(profile, prop, self.new_state[profile][prop])
            profile_changed = self.solve_link_list(profile,
                                                   self.old_state[profile]["links"],
                                                   self.new_state[profile]["links"])
            if profile_changed:
                self.difflog.update_profile(profile,
                                            self.new_state[profile]["beforeUpdate"],
                                            self.new_state[profile]["afterUpdate"])

    def _add_profiles(self, profiles):
        for profile in profiles:
            if profile in const.args.exclude:
                log_debug("'" + profile + "' is in exclude list. Skipping...")
                continue
            if profile not in self.old_state:
                self.difflog.add_profile(profile,
                                         self.new_state[profile]["beforeInstall"],
                                         self.new_state[profile]["afterInstall"])
                for prop in self.new_state[profile]:
                    if prop == "links":
                        continue
                    self.difflog.update_property(profile, prop, self.new_state[profile][prop])
                for link in self.new_state[profile]["links"]:
                    self.difflog.add_link(profile, link)

    def solve_included(self):
        # We begin with removing all profiles that are not in the new state
        old_profiles = self._remove_old_profiles(const.args.include)
        # Then we update all other profiles
        other_profiles = list(set(const.args.include) - set(old_profiles) - set(self.new_state.keys()))
        self._update_profiles(other_profiles)
        # Last we add profiles that are only in the new state
        self._add_profiles([p for p in const.args.include if p in self.new_state])

    def solve_all(self):
        # We begin with removing all profiles that are not in the new state
        old_profiles = self._remove_old_profiles(self.old_state.keys())
        # Then we update all profiles that occure in both
        other_profiles = list(set(self.old_state.keys()) - set(old_profiles))
        self._update_profiles(other_profiles)
        # Last we add profiles that are only in the new state
        self._add_profiles(self.new_state)


class UpdateDiffSolver(LinkListDiffSolver):
    """This solver determines the differences between treh current state file
    and a list of profiles.

    Attributes:
        state (State): The state file that is used for solving
        profile_results (dict): The result of the executed profiles
        parent(str): The name of the parent that all profiles will change
            its parent to (only set if ``--parent`` was specified)
    """
    def __init__(self, profile_results, parent):
        """ Constructor.

        Args:
            profile_results (list): A list of the result of the executed
                profiles
            parent (str): The value of the cli argument --parent
        """
        super().__init__()
        self.state = globalstate.current.copy()
        self.profile_results = profile_results
        self.parent = parent

    def _generate_operations(self):
        """Generates operations to update all profiles.

        This function resolves each root profile with their subprofiles
        separately.
        """
        for profile in self.profile_results:
            # Generate difflog from diff between profile result and state
            self.__generate_profile_link(profile, self.parent)

    def __generate_profile_link(self, profile_result, parent_name,
                                all_profilenames=[]):
        """Generate operations for resolving the differences between a single
        profile and the installed ones and appends the corresponding operations
        to the DiffLog for those differences. Calls itself recursively for all
        subprofiles.

        Args:
            profile_result (dict): The result of an executed profile that will be
                compared against the state file
            parent_name (str): The name of the profiles (new) parent. If
                parent_name is ``None``, the profile is treated as a root
                profile
        """

        def add_profilenames(profile):
            """Recursively add all names of subprofiles to all_profilenames"""
            all_profilenames.append(profile["name"])
            for prof in profile["profiles"]:
                add_profilenames(prof)
        if not all_profilenames:
            for profile in self.profile_results:
                add_profilenames(profile)

        # Checking exclude list
        profile_name = profile_result["name"]
        if profile_name in const.args.exclude:
            log_debug("'" + profile_name + "' is in exclude list. Skipping...")
            return
        # Get profile from state
        installed_profile = None
        if profile_name in self.state:
            installed_profile = self.state[profile_name]
            installed_links = installed_profile["links"]
            profile_new = False
        else:
            installed_links = []
            # The profile wasn't installed
            self.difflog.add_profile(profile_name, profile_result["beforeInstall"],
                                     profile_result["afterInstall"], parent_name)
            profile_new = True

        # Resolve differences betweeen links
        profile_changed = self.solve_link_list(profile_name, installed_links, profile_result["links"])

        # Remove all installed subprofiles that doesnt occur in profile anymore
        if installed_profile is not None:
            installed_subprofiles = set()
            profiles_subprofiles = set()
            # First get all subprofiles that were installed
            for installed_name, installed_dict in self.state.items():
                if "parent" in installed_dict:
                    if installed_dict["parent"] == profile_name:
                        installed_subprofiles.add(installed_name)
            # Then get all subprofiles that shall be installed
            if "profiles" in profile_result:
                for subprofile in profile_result["profiles"]:
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
            dfs = RemoveProfileDiffSolver(self.state, old_subprofiles)
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
                self.difflog.update_property(profile_name, "parent", parent_name)
            elif profile_changed and not profile_new:
                self.difflog.update_profile(profile_name,
                                            profile_result["beforeUpdate"],
                                            profile_result["afterUpdate"])

        # Update script properties, but only if they changed or the profile is new
        installed_profile = self.state.get(profile_name, {})
        events = ["beforeInstall", "afterInstall", "beforeUpdate",
                  "afterUpdate", "beforeUninstall", "afterUninstall"]
        for event in events:
            if profile_new or installed_profile.get(event, "") != profile_result[event]:
                self.difflog.update_property(profile_name, event, profile_result[event])

        # Recursive call for all subprofiles
        if "profiles" in profile_result:
            for subprofile in profile_result["profiles"]:
                self.__generate_profile_link(subprofile,
                                             profile_name,
                                             all_profilenames)
