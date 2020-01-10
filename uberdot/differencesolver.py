"""This module implements the Difference-Solvers (at the moment there is only
the standart DiffSolver) and their resulting data structure DiffLog.

.. autosummary::
    :nosignatures:

    DiffLog
    DiffSolver
"""

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


import copy
from uberdot.errors import FatalError
from uberdot.interpreters import Interpreter
from uberdot.utils import get_date_time_now
from uberdot.utils import import_profile_class
from uberdot.utils import log_warning
from uberdot.utils import normpath


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

    def add_info(self, profilename, message):
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
        # so interpreters can implement _op_start
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
    """This solver determines the differences between a list of profiles
    and an installed-file. It is used to generate a :class:`DiffLog` that
    stores all operations to resolve the differences between those.

    Attributes:
        profilenames (list): A list of names of all profiles that will be used
            for solving
        installed (dict): The installed-file that is used for solving
        difflog (DiffLog): The resulting DiffLog
        default_options (dict): The default options that the profiles will use
        default_dir (str): The default directory that profiles start in
        parent_arg (str): The name of the parent that all profiles will change
            its parent to (only set if ``--parent`` was specified)
    """
    def __init__(self, installed, args):
        """ Constructor. Initializes attributes from commandline arguments.

        Args:
            installed (dict): The installed-file that is used for solving
            args (argparse): The parsed arguments
        """
        self.profilenames = args.profiles
        self.installed = installed
        self.difflog = None
        self.default_options = args.opt_dict
        self.default_dir = args.directory
        self.parent_arg = args.parent

    def solve(self, update):
        """Start solving differences.

        Args:
            update (bool): True, if this an update. False if all links shall be
                removed (Yes, I know that's not intuitive but it wont stay like
                this).

        Returns:
            DiffLog: The resulting DiffLog
        """
        self.difflog = DiffLog()
        if update:
            self.__generate_links()
        else:
            self.__generate_unlinks(self.profilenames)
        return self.difflog

    def __generate_unlinks(self, profilelist):
        """Generates operations to remove all installed profiles of
        ``profilelist``.

        Skips profiles that are not installed.

        Args:
            profilelist (list): A list of names of profiles that will be
                unlinked
        """
        for profilename in profilelist:
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
        # Recursive call for all subprofiles
        subprofiles = []
        for installed_name, installed_dict in self.installed.items():
            if ("parent" in installed_dict and
                    installed_dict["parent"] == profile_name):
                subprofiles.append(installed_name)
        self.__generate_unlinks(subprofiles)
        # We are removing all symlinks of this profile before we
        # remove the profile from the installed file
        installed_links = copy.deepcopy(self.installed[profile_name]["links"])
        for installed_link in installed_links:
            self.difflog.remove_link(installed_link["name"], profile_name)
        self.difflog.remove_profile(profile_name)

    def __generate_links(self):
        """Generates operations to update all profiles.

        This function imports and runs the profiles and resolves each root
        profile with their subprofiles separately.
        """
        allpnames = []

        def add_profilenames(profile):
            """Recursively add all subprofiles to allpnames"""
            allpnames.append(profile["name"])
            for prof in profile["profiles"]:
                add_profilenames(prof)

        # Setting arguments for root profiles
        pargs = {}
        pargs["options"] = self.default_options
        pargs["directory"] = self.default_dir

        plist = []
        for profilename in self.profilenames:
            # Profiles are generated
            plist.append(
                import_profile_class(profilename)(**pargs).generator()
            )
        for profileresult in plist:
            add_profilenames(profileresult)
        for profileresult in plist:
            # Generate difflog from diff between links and installed
            self.__generate_profile_link(profileresult, allpnames,
                                         self.parent_arg)

    def __generate_profile_link(self, profile_dict, all_profilenames,
                                parent_name):
        """Resolves the differences between a single profile and the installed
        ones and appends the corresponding operations to the DiffLog for those
        differences. Calls itself recursively for all subprofiles.

        Args:
            profile_dict (dict): The result of an executed profile that will be
                compared against the installed-file
            all_profilenames (list): A list with all profile names (including
                all sub- and root-profiles)
            parent_name (str): The name of the profiles (new) parent. If
                parent_name is ``None``, the profile is treated as a root
                profile
        """
        def symlinks_similar(symlink1, symlink2):
            return normpath(symlink1["name"]) == normpath(symlink2["name"]) or \
                   normpath(symlink1["target"]) == normpath(symlink2["target"])
        def symlinks_equal(symlink1, symlink2):
            return normpath(symlink1["name"]) == normpath(symlink2["name"]) and \
                   normpath(symlink1["target"]) == normpath(symlink2["target"]) and \
                   symlink1["uid"] == symlink2["uid"] and \
                   symlink1["gid"] == symlink2["gid"] and \
                   symlink1["permission"] == symlink2["permission"] and\
                   symlink1["secure"] == symlink2["secure"]


        profile_new = False
        profile_changed = False

        # Load the links from the InstalledLog
        profile_name = profile_dict["name"]
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
        # To do this we actually compare installed_links with new_links
        # and check which links:
        #   - didn't changed (must be the same in both)
        #   - are removed (occure only in installed_links)
        #   - are updated (two links that differ, but only in one property)
        #   - are added (occure only in new_links)
        # Whenever we find a link to be unchanged/removed/etc. we will remove
        # it from new_links and installed_links, so in the end both lists
        # need to be empty.

        # Check unchanged
        count = 0
        for installed_link in installed_links[:]:
            for new_link in new_links[:]:
                if symlinks_equal(installed_link, new_link):
                    # Link in new profile is the same as a installed one,
                    # so ignore it
                    installed_links.remove(installed_link)
                    new_links.remove(new_link)
                    count += 1
                    break
        if count > 0:
            msg = str(count)
            msg += " links will be left untouched, no changes here..."
            self.difflog.add_info(profile_name, msg)

        # Check removed
        for installed_link in installed_links[:]:
            remove = True
            for new_link in new_links[:]:
                if symlinks_similar(installed_link, new_link):
                    remove = False
                    break
            if remove:
                # Installed link is not similiar to any new link, so remove it
                profile_changed = True
                self.difflog.remove_link(installed_link["name"], profile_name)
                installed_links.remove(installed_link)

        # Check changed and added links
        for new_link in new_links[:]:
            add = True
            for installed_link in installed_links[:]:
                if symlinks_similar(installed_link, new_link):
                    # Update links that changed in only a few properties
                    profile_changed = True
                    self.difflog.update_link(installed_link, new_link,
                                             profile_name)
                    installed_links.remove(installed_link)
                    new_links.remove(new_link)
                    add = False
                    break
            if add:
                # There was no similar installed link, so we need to add it
                profile_changed = True
                self.difflog.add_link(new_link, profile_name)
                new_links.remove(new_link)

        # We removed every symlinks from new_links and installed_links when
        # we found the correct action for them. If they aren't empty now,
        # something obiously went wrong. We are checking for this
        # invariant to spot possible logical errors.
        if new_links or installed_links:
            raise FatalError("Couldn't resolve differences between the " +
                             "installed and the new version of profile " +
                             profile_name)

        # Remove all installed subprofiles that doesnt occur in profile anymore
        if installed_profile is not None:
            installed_subprofiles = set()
            profiles_subprofiles = set()
            for installed_name, installed_dict in self.installed.items():
                if ("parent" in installed_dict and
                        installed_dict["parent"] == profile_name):
                    installed_subprofiles.add(installed_name)
            if "profiles" in profile_dict:
                for subprofile in profile_dict["profiles"]:
                    profiles_subprofiles.add(subprofile["name"])
            old_subprofiles = [item for item in installed_subprofiles
                               if item not in profiles_subprofiles]
            for i in range(len(old_subprofiles)-1, -1, -1):
                # Don't unlink old subprofiles that only changed their parent
                if old_subprofiles[i] in all_profilenames:
                    old_subprofiles.pop(i)
            self.__generate_unlinks(old_subprofiles)

        # If something in the profile changed we need to update
        # its modification date and maybe its parent too
        if installed_profile is not None:
            if parent_name != (installed_profile["parent"]
                               if "parent" in installed_profile else None):
                self.difflog.update_parent(profile_name, parent_name)
            elif profile_changed and not profile_new:
                self.difflog.update_profile(profile_name)

        # Recursive call
        if "profiles" in profile_dict:
            for subprofile in profile_dict["profiles"]:
                self.__generate_profile_link(subprofile,
                                             all_profilenames,
                                             profile_name)
