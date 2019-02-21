"""This module implements the Difference-Solver"""

###############################################################################
#
# Copyright 2018 Erik Schulz
#
# This file is part of Dotmanager.
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
# Diese Datei ist Teil von Dotmanger.
#
# Dotmanger ist Freie Software: Sie können es unter den Bedingungen
# der GNU General Public License, wie von der Free Software Foundation,
# Version 3 der Lizenz oder (nach Ihrer Wahl) jeder neueren
# veröffentlichten Version, weiter verteilen und/oder modifizieren.
#
# Dotmanger wird in der Hoffnung, dass es nützlich sein wird, aber
# OHNE JEDE GEWÄHRLEISTUNG, bereitgestellt; sogar ohne die implizite
# Gewährleistung der MARKTFÄHIGKEIT oder EIGNUNG FÜR EINEN BESTIMMTEN ZWECK.
# Siehe die GNU General Public License für weitere Details.
#
# Sie sollten eine Kopie der GNU General Public License zusammen mit diesem
# Programm erhalten haben. Wenn nicht, siehe <https://www.gnu.org/licenses/>.
#
###############################################################################


import copy
from dotmanager import constants
from dotmanager.differencelog import DiffLog
from dotmanager.errors import FatalError
from dotmanager.utils import import_profile_class
from dotmanager.utils import log_warning


class DiffSolver():
    """Takes a list of profilenames and the currend install-file.
    Generates a the ProfileResults from the profiles and compares it
    with the installed-file. It will then generate a DiffLog that
    solves the difference between those two"""
    def __init__(self, installed, args):
        self.profilenames = args.profiles
        self.installed = installed
        self.difflog = None
        self.defs = {}
        self.default_options = args.opt_dict
        self.default_dir = args.directory
        self.parent_arg = args.parent

    def solve(self, link):
        """This will create an DiffLog from the set profiles"""
        self.defs = {}
        self.difflog = DiffLog()
        if link:
            self.__generate_links()
        else:
            self.__generate_unlinks(self.profilenames)
        return self.difflog

    def __generate_unlinks(self, profilelist):
        """Fill the difflog with all operations needed to
        unlink multiple profiles"""
        for profilename in profilelist:
            if profilename in self.installed:
                self.__generate_profile_unlink(profilename)
            else:
                log_waring("The profile " + profilename +
                              " is not installed at the moment. Skipping...")

    def __generate_profile_unlink(self, profile_name):
        """Append to difflog that we want to remove a profile,
        all it's subprofiles and all their links"""
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
        """Fill the difflog with all operations needed to link all profiles"""
        allpnames = []

        def add_profilenames(profile):
            """Recursively add all subprofiles to allpnames"""
            allpnames.append(profile["name"])
            for prof in profile["profiles"]:
                add_profilenames(prof)

        pargs = {}
        # Merge options provided by commandline with loaded defaults
        if self.default_options:
            pargs["options"] = {**constants.DEFAULTS, **self.default_options}
        # Same for directory
        if self.default_dir:
            pargs["directory"] = self.default_dir

        plist = []
        for profilename in self.profilenames:
            # Profiles are generated
            plist.append(import_profile_class(profilename)(**pargs).get())
        for profileresult in plist:
            add_profilenames(profileresult)
        for profileresult in plist:
            # Generate difflog from diff between links and installed
            self.__generate_profile_link(profileresult, allpnames,
                                         self.parent_arg)

    def __generate_profile_link(self, profile_dict, all_profilenames,
                                parent_name):
        """Resolves the differences between a single profile and the installed
        ones and appends the difflog for those. If parent_name is None the
        profile is treated as a root profile"""
        def symlinks_similar(symlink1, symlink2):
            return symlink1["name"] == symlink2["name"] or \
                   symlink1["target"] == symlink2["target"]

        def symlinks_equal(symlink1, symlink2):
            return symlink1["name"] == symlink2["name"] and \
                   symlink1["target"] == symlink2["target"] and \
                   symlink1["uid"] == symlink2["uid"] and \
                   symlink1["gid"] == symlink2["gid"] and \
                   symlink1["permission"] == symlink2["permission"]

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
        # and check which links:_
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
                    # Update links that changed in only one or two properties
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
