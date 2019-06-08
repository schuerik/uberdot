"""
This module contains all the different Interpreters.
Interpreters implement the behavior for all or a subset of operations of a
DiffLog. That way interpreters encapsulate behavior, checks and actions of
operations, that can be turned on and off freely.
Some examples what interpreters do:

    - Checking if operations contradict each other
    - Logging/Printing an operation
    - Gaining root access if an operation needs them
    - Actually create links according to the operations
"""

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
###############################################################################


import grp
import hashlib
import logging
import os
import pwd
import re
import sys
from abc import abstractmethod
from shutil import copyfile
from subprocess import PIPE
from subprocess import Popen
from dotmanager import constants
from dotmanager.errors import IntegrityError
from dotmanager.errors import PreconditionError
from dotmanager.errors import UnkownError
from dotmanager.errors import UserError
from dotmanager.errors import UserAbortion
from dotmanager.errors import FatalError
from dotmanager.utils import find_files
from dotmanager.utils import get_date_time_now
from dotmanager.utils import get_dir_owner
from dotmanager.utils import get_gid
from dotmanager.utils import get_uid
from dotmanager.utils import is_dynamic_file
from dotmanager.utils import log_warning
from dotmanager.utils import normpath


logger = logging.getLogger("root")


class Interpreter():
    """Base-class for an interpreter.

    Attributes:
        data (List): The raw DiffLog that is interpreted.
            Only needed by Interpreters that alter the DiffLog.
    """
    def __init__(self):
        """Constructor"""
        self.data = None

    def set_difflog_data(self, data):
        """Sets the DiffLogData.

        Needed by Interpreters that alter the DiffLog.

        Args:
            data (List): The raw DiffLog that will be set
        """
        self.data = data

    def call_operation(self, operation):
        """Call the implemented behavior for this operation.

        This calls a function named like ``operation["operation"]`` with
        the prefix '_op_', if the function was implemented by the interpreter.

        Args:
            operation (Dict): A operation from DiffLog
        """
        # Check if this interpreter has implemented the operation, then call
        attribute = getattr(self, "_op_" + operation["operation"], None)
        if callable(attribute):
            attribute(operation)


class PlainPrintInterpreter(Interpreter):
    """Prints add/remove/update-operation without any formating."""
    def __init__(self):
        """Constructor.

        Maps ``_op_*`` functions to ``print()``.
        """
        super().__init__()
        self._op_add_p = self._op_remove_p = self._op_update_p = print
        self._op_add_l = self._op_remove_l = self._op_update_l = print

    def _op_start(self, dop):
        """Print "[" to show the start of an array.

        Args:
            dop (Dict): Unused in this implementation
        """
        print("[")

    def _op_fin(self, dop):
        """Print "]" to show the end of an array.

        Args:
            dop (Dict): Unused in this implementation
        """
        print("]")


class PrintInterpreter(Interpreter):
    """Pretty-prints log messages and what a operation is going to do."""
    @staticmethod
    def _log_interpreter(dop, message):
        """Logs/Prints out a message for an operation.

        Args:
            dop (Dict): The operation that is logged. Used to include the
                profile name in the log message that triggered the operation.
            message (str): The message that will be logged
        """
        logger.info(constants.BOLD + "[" + dop["profile"] + "]: " +
                    constants.NOBOLD + message)

    def _op_start(self, dop):
        """Logs/Prints out the start of the linking process.

        Args:
            dop (Dict): Unused in this implementation
        """
        logger.debug("Starting linking process now.")

    def _op_info(self, dop):
        """Logs/Prints out an info-operation.

        Args:
            dop (Dict): The info-operation that will be logged
        """
        self._log_interpreter(dop, dop["message"])

    def _op_add_p(self, dop):
        """Logs/Prints out that a profile was added.

        Args
            dop (Dict): The add-operation that will be logged
        """
        if dop["parent"] is not None:
            self._log_interpreter(dop, "Installing new profile as" +
                                  " subprofile of " + dop["parent"])
        else:
            self._log_interpreter(dop, "Installing new profile")

    def _op_remove_p(self, dop):
        """Logs/Prints out that a profile was removed.

        Args
            dop (Dict): The remove-operation that will be logged
        """
        self._log_interpreter(dop, "Uninstalled profile")

    def _op_update_p(self, dop):
        """Logs/Prints out that a profile was updated.

        Args
            dop (Dict): The update-operation that will be logged
        """
        if "parent" in dop:
            if dop["parent"] is not None:
                self._log_interpreter(dop, "Changed parent to '" +
                                      dop["parent"] + "'")
            else:
                self._log_interpreter(dop, "Detached from parent." +
                                      " This is a root profile now.")
        self._log_interpreter(dop, "Profile updated")

    def _op_add_l(self, dop):
        """Logs/Prints out that a link was added.

        Args
            dop (Dict): The add-operation that will be logged
        """
        self._log_interpreter(dop, dop["symlink"]["name"] +
                              " was created and links to " +
                              dop["symlink"]["target"])

    def _op_remove_l(self, dop):
        """Logs/Prints out that a link was removed.

        Args
            dop (Dict): The remove-operation that will be logged
        """
        self._log_interpreter(dop, dop["symlink_name"] +
                              " was removed from the system.")

    def _op_update_l(self, dop):
        """Logs/Prints out that a link was updated.

        The message is generated according to what changed in the updated link.

        Args
            dop (Dict): The update-operation that will be logged
        """
        if dop["symlink1"]["name"] != dop["symlink2"]["name"]:
            self._log_interpreter(dop, dop["symlink1"]["name"] +
                                  " was moved to " + dop["symlink2"]["name"])
        elif dop["symlink2"]["target"] != dop["symlink1"]["target"]:
            self._log_interpreter(dop, dop["symlink1"]["name"] +
                                  " points now to " +
                                  dop["symlink2"]["target"])
        else:
            msg = dop["symlink1"]["name"] + " has changed "
            if dop["symlink2"]["permission"] != dop["symlink1"]["permission"]:
                msg += "permission from " + str(dop["symlink1"]["permssion"])
                msg += " to " + str(dop["symlink2"]["permssion"])
                self._log_interpreter(dop, msg)
            elif dop["symlink2"]["uid"] != dop["symlink1"]["uid"] or \
                    dop["symlink2"]["gid"] != dop["symlink1"]["gid"]:
                user = pwd.getpwuid(dop["symlink1"]["uid"])[0]
                group = grp.getgrgid(dop["symlink1"]["gid"])[0]
                msg += "owner from " + user + ":" + group
                user = pwd.getpwuid(dop["symlink2"]["uid"])
                group = grp.getgrgid(dop["symlink2"]["gid"])
                msg += " to " + user + ":" + group
                self._log_interpreter(dop, msg)


class DUIStrategyInterpreter(Interpreter):
    """Reorders DiffLog so linking won't be in the order of profiles but
    instead in the order Delete-Update-Insert. It also removes log messages
    because without the old order they are not useful anymore.

    Attributes:
        profile_deletes (List): A collection for profile-remove-operations
        profile_updates (List): A collection for profile-update-operations
        profile_adds (List): A collection for profile-add-operations
        link_deletes (List): A collection for link-remove-operations
        link_updates (List): A collection for link-update-operations
        link_adds (List): A collection for link-add-operations
    """
    def __init__(self):
        super().__init__()
        self.profile_deletes = []
        self.profile_updates = []
        self.profile_adds = []
        self.link_deletes = []
        self.link_updates = []
        self.link_adds = []

    def _op_add_p(self, dop):
        """Adds the profile-add-operation to ``profile_adds``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.profile_adds.append(dop)

    def _op_remove_p(self, dop):
        """Adds the profile-remove-operation to ``profile_removes``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.profile_deletes.append(dop)

    def _op_update_p(self, dop):
        """Adds the profile-update-operation to ``profile_updates``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.profile_updates.append(dop)

    def _op_add_l(self, dop):
        """Adds the link-add-operation to ``link_adds``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.link_adds.append(dop)

    def _op_remove_l(self, dop):
        """Adds the link-remove-operation to ``link_removes``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.link_deletes.append(dop)

    def _op_update_l(self, dop):
        """Adds the link-update-operation to ``link_updates``.

        Args:
            dop (Dict): The operation that will be added
        """
        self.link_updates.append(dop)

    def _op_fin(self, dop):
        """Merges the collections of operations in the correct order
        and overwrites ``self.data`` to alter the DiffLog

        Args:
            dop (Dict): Unused in this implementation
        """
        merged_list = self.profile_deletes + self.profile_updates
        merged_list += self.profile_adds + self.link_deletes
        merged_list += self.link_updates + self.link_adds
        self.data.clear()
        for item in merged_list:
            self.data.append(item)


class CheckDynamicFilesInterpreter(Interpreter):
    """Checks if there are changes to a dynamic file and
    gives the user the oppoutunity to interact with them.

    Attributes:
        dryrun (bool): Stores, if ``--dryrun`` was set
    """

    def __init__(self, dryrun):
        """Constructor.

        Args:
            dryrun (bool): Sets, if this is a dryrun
        """
        self.dryrun = dryrun

    def _op_update_l(self, dop):
        """Inspects the target file of the to be updated link.

        Args:
            dop (Dict): The update-operation of the to be updated link
        """
        self.inspect_file(dop["symlink1"]["target"])

    def _op_remove_l(self, dop):
        """Inspects the target file of the to be removed link.

        Args:
            dop (Dict): The remove-operation of the to be removed link
        """
        self.inspect_file(os.readlink(dop["symlink_name"]))

    def inspect_file(self, target):
        """Checks if a file is dynamic and was changed. If so, it
        calls a small UI to store/undo changes.

        Args:
            target (str): The full path to the file that will be checked
        """
        if not target.startswith(constants.DATA_DIR):
            # This is not a dynamic file
            return
        # Calculate new hash and get old has of file
        md5_calc = hashlib.md5(open(target, "rb").read()).hexdigest()
        md5_old = os.path.basename(target)[-32:]
        # Check for changes
        if is_dynamic_file(target) and md5_calc != md5_old:
            log_warning("You made changes to '" + target + "'. Those changes" +
                        " will be lost, if you don't write them back to" +
                        " the original file.")
            self.user_interaction(target)

    def user_interaction(self, target):
        """Provides a small UI for the user to interact with a changed dynamic
        file.

        The user can choose one of the following options to handle the changes:

            - **A**: Abort and exit Dotmanager
            - **I**: Ignore the changes and do nothing
            - **D**: Show a diff and ask again
            - **P**: Create a patch file and ask again
            - **U**: Undo the changes and restore the original file

        Args:
            target (str): The full path to the file that the user will interact
                with
        Raises:
            UserAbortion: The user decided to abort the whole process
            PreconditionError: The patch file could not be written
        """
        target_bak = target + "." + constants.BACKUP_EXTENSION
        done = False
        while not done:
            inp = input("[A]bort / [I]gnore / Show [D]iff " +
                        "/ Create [P]atch / [U]ndo changes: ")
            if inp == "A":
                raise UserAbortion
            if inp == "I":
                done = True
            elif inp == "D":
                # Create a colored diff between the file and its original
                process = Popen(["diff", "--color=auto", target_bak, target])
                process.communicate()
            elif inp == "P":
                # Create a git patch with git diff
                patch_file = os.path.join(constants.TARGET_FILES,
                                          os.path.basename(target))
                patch_file += ".patch"
                patch_file = input("Enter filename for patch [" +
                                   patch_file + "]: ") or patch_file
                args = ["git", "diff", "--no-index", target_bak, target]
                process = Popen(args, stdout=PIPE)
                try:
                    with open(patch_file, "wb") as file:
                        file.write(process.stdout.read())
                    print("Patch file written successfully")
                except IOError:
                    msg = "Could not write patch file '" + patch_file + "'."
                    raise PreconditionError(msg)
            elif inp == "U":
                if self.dryrun:
                    print("This does nothing this time since " +
                          "this is just a dry-run")
                else:
                    # Copy the original to the changed
                    copyfile(target_bak, target)
                done = True
            else:
                log_warning("Invalid option")


class CheckLinksInterpreter(Interpreter):
    """Checks for conflicts between all links.

    Conflicts are things like duplicates, multiple targets / overwrites, etc.

    Args:
        linklist (List): List that stores all links, their corresponding
            profiles and if they are already installed. Links that are already
            installed and won't be removed, will end up twice in this list.
    """
    def __init__(self, installed):
        """Constructor.

        Initializes ``linklist`` with all links from the installed-file.

        Args:
            installed (Dict): The installed file, that was used to create the
                current DiffLog
        """
        super().__init__()
        # Setup linklist to store/lookup which links are modified
        # Stores for any link: (linkname, profile, is_installed)
        self.linklist = []
        for key, profile in installed.items():
            if key[0] != "@":  # Ignore special entrys like @version
                for link in profile["links"]:
                    self.linklist.append((link["name"], profile["name"], True))

    def _op_add_l(self, dop):
        """Checks if the to be added link already occurs in ``linklist``.

        This would be forbidden, because a link that is already installed can't
        be added again (only updated). Similary it would be forbidden to add a
        link that was already added by another profile in the same run.
        If everything is valid, the link will be added to the list.

        Args:
            dop (Dict): The add-operation that will be checked
        Raises:
            IntegrityError: The check failed
        """
        name = dop["symlink"]["name"]
        for item in self.linklist:
            if item[0] == name:
                if item[2]:
                    msg = " installed "
                else:
                    msg = " defined "
                msg = "The link '" + name + "' is already" + msg + "by '"
                msg += item[1] + "' and would be overwritten by '"
                msg += dop["profile"] + "'."
                raise IntegrityError(msg)
        self.linklist.append((name, dop["profile"], False))

    def _op_remove_l(self, dop):
        """Removes link from linklist because links could be removed and
        added in one run by different profiles.

        In that case it would look like the link is added even though it is
        already installed if we don't remove it here.

        Args:
            dop (Dict): The remove-operation that will be used to remove the
                link
        """
        count = 0
        for item in self.linklist:
            if item[0] == dop["symlink_name"]:
                break
            count += 1
        if count == len(self.linklist):
            raise FatalError("Can't remove link that isn't installed")
        self.linklist.pop(count)


class CheckLinkBlacklistInterpreter(Interpreter):
    """Checks if a operation touches a link that is on the blacklist.

    Attributes:
        superforce (bool): Stores, if ``--superforce`` was set
        blacklist (List): A list of file name patterns that are forbidden
            to touch without superforce flag
    """
    def __init__(self, superforce):
        """Constructor.

        Loads the blacklist.

        Args:
            superforce (bool): Sets, if superforce was turned on
        """
        super().__init__()
        self.superforce = superforce
        self.blacklist = []
        for bl in find_files("black.list", constants.CONFIG_SEARCH_PATHS):
            with open(bl, "r") as file:
                for line in file.readlines():
                    self.blacklist.append(line)
        self.blacklist = [entry.strip() for entry in self.blacklist]

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
            if re.search(entry, file_name):
                log_warning("You are trying to " + action + " '" + file_name +
                            "' which is blacklisted. It is considered " +
                            "dangerous to " + action + " those files!")
                if self.superforce:
                    log_warning("Are you sure that you want to " + action +
                                " a blacklisted file?")
                    confirmation = input("Type \"YES\" to confirm or " +
                                         "anything else to cancel: ")
                    if confirmation != "YES":
                        raise UserAbortion
                else:
                    log_warning("If you really want to modify this file" +
                                " you can use the --superforce flag to" +
                                " ignore the blacklist.")
                    raise IntegrityError("Won't " + action +
                                         " blacklisted file!")

    def _op_update_l(self, dop):
        """Checks the old and the new symlink for blacklist violations.

        Args:
            dop (Dict): The update-operation whose symlinks will be checked
        """
        if dop["symlink1"]["name"] == dop["symlink2"]["name"]:
            self.check_blacklist(dop["symlink1"]["name"], "update")
        else:
            self.check_blacklist(dop["symlink1"]["name"], "remove")
            self.check_blacklist(dop["symlink2"]["name"], "overwrite")

    def _op_remove_l(self, dop):
        """Checks the to be removed symlink for blacklist violations.

        Args:
            dop (Dict): The remove-operation whose symlink will be checked
        """
        self.check_blacklist(dop["symlink_name"], "remove")

    def _op_add_l(self, dop):
        """Checks the to be added symlink for blacklist violations.

        Args:
            dop (Dict): The add-operation whose symlink will be checked
        """
        self.check_blacklist(dop["symlink"]["name"], "overwrite")


class CheckLinkDirsInterpreter(Interpreter):
    """Checks if directories need to be created.

    Attributes:
        makedirs (bool): Stores, if ``--makedirs`` was set
    """
    def __init__(self, makedirs):
        """Constructor

        Args:
            dryrun (bool): Sets, if directories shall be created
        """
        super().__init__()
        self.makedirs = makedirs

    def _op_add_l(self, dop):
        """Checks if the directory of the to be added link already exists.

        Args:
            dop (Dict): The add-operation whose symlink will be checked
        """
        self.check_dirname(os.path.dirname(dop["symlink"]["name"]))

    def _op_update_l(self, dop):
        """Checks if the directory of the to be updated link already exists.

        Args:
            dop (Dict): The update-operation whose symlink will be checked
        """
        self.check_dirname(os.path.dirname(dop["symlink2"]["name"]))

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


class CheckLinkExistsInterpreter(Interpreter):
    """Checks if links of installed-file really exist in the filesystem.

    Attributes:
        force (bool): Stores, if ``--force`` was set
        removed_links (List): A collection of all links that are going to be
            removed
    """
    def __init__(self, force):
        """Constructor"""
        super().__init__()
        self.force = force
        self.removed_links = []

    def _op_remove_l(self, dop):
        """Checks if the to be removed link really exists.

        Furthermore adds the link to ``removed_links``, because removed links
        need to be stored for ``_op_add_l()``.

        Args:
            dop (Dict): The remove-operation that will be checked
        Raises:
            PreconditionError: The to be removed link does not exist
        """
        if not os.path.lexists(dop["symlink_name"]):
            msg = "'" + dop["symlink_name"] + "' can not be removed because"
            msg += " removed because it does not exist on your filesystem."
            msg += " Check your installed file!"
            raise PreconditionError(msg)
        self.removed_links.append(dop["symlink_name"])

    def _op_update_l(self, dop):
        """Checks if old and the new link already exist.

        Furthermore adds the old link to ``removed_links`` if old and new link
        have different names, because removed links need to be stored for
        ``_op_add_l()``.

        Args:
            dop (Dict): The update-operation that will be checked
        Raises:
            PreconditionError: The to be old link does not exist, the new
                link already exists or the new link points to a non-existent
                file
        """
        if not os.path.lexists(dop["symlink1"]["name"]):
            msg = "'" + dop["symlink1"]["name"] + "' can not be updated"
            msg += " because it does not exist on your filesystem."
            msg += " Check your installed file!"
            raise PreconditionError(msg)
        if (dop["symlink1"]["target"] != dop["symlink2"]["target"] and
                os.path.exists(dop["symlink2"]["target"])):
            msg = "'" + dop["symlink1"]["name"] + "' will not be updated"
            msg += " to point to '" + dop["symlink2"]["target"] + "'"
            msg += " because '" + dop["symlink2"]["target"]
            msg += "' does not exist in your filesystem."
            raise PreconditionError(msg)
        if dop["symlink1"]["name"] != dop["symlink2"]["name"]:
            if os.path.lexists(dop["symlink2"]["name"]):
                msg = "'" + dop["symlink1"]["name"] + "' can not be moved to '"
                msg += dop["symlink2"]["name"] + "' because it already exist"
                msg += " on your filesystem and would be overwritten."
                raise PreconditionError(msg)
            self.removed_links.append(dop["symlink1"]["name"])

    def _op_add_l(self, dop):
        """Checks if the new link already exists.

        Args:
            dop (Dict): The add-operation that will be checked
        Raise:
            PreconditionError: The new link already exists or its target does
                not exist
        """
        if (not dop["symlink"]["name"] in self.removed_links and
                not self.force and os.path.lexists(dop["symlink"]["name"])):
            msg = "'" + dop["symlink"]["name"] + "' already exists and"
            msg += " would be overwritten. You can force to overwrite the"
            msg += " original file by setting the --force flag."
            raise PreconditionError(msg)
        if not os.path.exists(dop["symlink"]["target"]):
            msg = "'" + dop["symlink"]["name"] + "' will not be created"
            msg += " because it points to '" + dop["symlink"]["target"]
            msg += "' which does not exist in your filesystem."
            raise PreconditionError(msg)


class CheckProfilesInterpreter(Interpreter):
    """Checks if profiles can be installed together. Protects against
    duplicates and overwrites.

    Attributes:
        parnent_arg (str): Stores the value of ``--parent``
        profile_list (List): A list that stores all profiles, their parents
            and if they are already installed. Profiles that are still
            installed in the end, will end up twice in this list.
    """
    def __init__(self, installed, parent_arg=None):
        """Constructor.

        Initializes ``profile_list`` with all profiles from the installed-file.

        Args:
            installed (Dict): The installed file, that was used to create the
                DiffLog
            parent_arg (str): The value of ``--parent``
        """
        super().__init__()
        self.parent_arg = parent_arg
        self.profile_list = []
        # profile_list contains: (profile name, parent name, is installed)
        for key, profile in installed.items():
            if key[0] != "@":
                self.profile_list.append(
                    (profile["name"],
                     profile["parent"] if "parent" in profile else None, True))

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
            dop (Dict): The add-operation that will be checked
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
            dop (Dict): The update-operation that will be checked
        Raises:
            IntegrityError: A profile installed as a subprofile of another root
                profile
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
                if self.parent_arg == dop["parent"]:
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


class ExecuteInterpreter(Interpreter):
    """This interpreter actually executes the operations from the DiffLog.

    It can create/delete links in the filesystem and modify the installed-file.

    Attributes:
        installed (Dict): The installed-file that will be updated
        force (bool): Stores, if ``--force`` was set
    """
    def __init__(self, installed, force):
        """Constructor.

        Updates the version number of the installed-file.

        Args:
            installed (Dict): The installed-file that will be updated
            force (bool): The value of ``--force``
        """
        super().__init__()
        self.installed = installed
        self.installed["@version"] = constants.VERSION  # Update version number
        self.force = force

    def _op_add_p(self, dop):
        """Adds a profile entry of the installed-file.

        Args:
            dop (Dict): The add-operation that will be executed
        """
        new_profile = {}
        new_profile["name"] = dop["profile"]
        new_profile["links"] = []
        new_profile["installed"] = new_profile["updated"] = get_date_time_now()
        if dop["parent"] is not None:
            new_profile["parent"] = dop["parent"]
        self.installed[new_profile["name"]] = new_profile

    def _op_remove_p(self, dop):
        """Removes a profile entry of the installed-file.

        Args:
            dop (Dict): The remove-operation that will be executed
        """
        del self.installed[dop["profile"]]

    def _op_update_p(self, dop):
        """Updates a profile entry of the installed-file.

        Args:
            dop (Dict): The update-operation that will be executed
        """
        if "parent" in dop:
            if dop["parent"] is not None:
                self.installed[dop["profile"]]["parent"] = dop["parent"]
            elif "parent" in self.installed[dop["profile"]]:
                del self.installed[dop["profile"]]["parent"]
        self.installed[dop["profile"]]["updated"] = get_date_time_now()

    def _op_add_l(self, dop):
        """Adds a link to the filesystem and adds a link entry of the
        corresponding profile in the installed-file.

        Args:
            dop (Dict): The add-operation that will be executed
        """
        self.__create_symlink(dop["symlink"]["name"],
                              dop["symlink"]["target"],
                              dop["symlink"]["uid"],
                              dop["symlink"]["gid"],
                              dop["symlink"]["permission"])
        self.installed[dop["profile"]]["links"].append(dop["symlink"])

    def _op_remove_l(self, dop):
        """Removes a link from the filesystem and removes the links entry of
        the corresponding profile in the installed-file.

        Args:
            dop (Dict): The remove-operation that will be executed
        """
        os.unlink(dop["symlink_name"])
        for link in self.installed[dop["profile"]]["links"]:
            if link["name"] == dop["symlink_name"]:
                self.installed[dop["profile"]]["links"].remove(link)

    def _op_update_l(self, dop):
        """Updates a link in the filesystem and updates the links entry of
        the corresponding profile in the installed-file.

        Args:
            dop (Dict): The update-operation that will be executed
        """
        os.unlink(dop["symlink1"]["name"])
        self.__create_symlink(dop["symlink2"]["name"],
                              dop["symlink2"]["target"],
                              dop["symlink2"]["uid"],
                              dop["symlink2"]["gid"],
                              dop["symlink2"]["permission"])
        self.installed[dop["profile"]]["links"].remove(dop["symlink1"])
        self.installed[dop["profile"]]["links"].append(dop["symlink2"])

    def __create_symlink(self, name, target, uid, gid, permission):
        """Create a symlink in the filesystem.

        Args:
            name (str): The full path of the link that will be created
            target (str): The full path of the file that the link will
                point to
            uid (int): The UID of the owner of the link
            gid (int): The GID of the owner of the link
            permission (int): The permissions of the target
        Raises:
            UnkownError: The link could not be created
        """
        if not os.path.isdir(os.path.dirname(name)):
            self._makedirs(name)
        try:
            # Remove existing symlink
            if self.force and os.path.lexists(name):
                os.unlink(name)
            # Create new symlink
            os.symlink(target, name)
            # Set owner and permission
            os.lchown(name, uid, gid)
            if permission != 644:
                os.chmod(name, int(str(permission), 8))
        except OSError as err:
            raise UnkownError(err, "An unkown error occured when trying to" +
                              " create the link '" + name + "'.")

    @staticmethod
    def _makedirs(filename):
        """Custom ``os.makedirs()`` that keeps the owner of the directory.

        This means that it will create the directory with the owner of the
        deepest directory that already exists instead of using current user as
        owner. This is needed, because otherwise directories won't be
        accessible by the user, if some links would be created with root
        permissions.

        Args:
            filename (str): The full path of the file that needs its
                directories created
        """
        # First find the deepest directory of the path that exists
        dirname = os.path.dirname(filename)
        while not os.path.isdir(dirname):
            dirname = os.path.dirname(dirname)
        # And remember its owner
        uid, gid = os.stat(dirname).st_uid, os.stat(dirname).st_gid
        top_dir = dirname
        # Then create directories
        dirname = os.path.dirname(filename)
        os.makedirs(dirname)
        # And change owner of all created directories to the remembered owner
        while dirname != top_dir:
            os.chown(dirname, uid, gid)
            dirname = os.path.dirname(dirname)


class DetectRootInterpreter(Interpreter):
    """Checks if root permission is needed to perform operations. """

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
        dirname = os.path.dirname(path)
        if os.access(dirname, os.W_OK):
            return True
        return self._access(dirname)

    def _op_add_l(self, dop):
        """Checks if new links are either created in inaccessible directories
        or will be owned by other users than the current.

        Args:
            dop (Dict): The add-operation that will be checked
        """
        name = dop["symlink"]["name"]
        uid, gid = get_dir_owner(name)
        if dop["symlink"]["uid"] != uid or dop["symlink"]["gid"] != gid:
            self._root_detected(dop, "change owner of", name)
        elif not self._access(name):
            self._root_detected(dop, "create links in", os.path.dirname(name))

    def _op_remove_l(self, dop):
        """Checks if to be removed links are owned by other users than
        the current.

        Args:
            dop (Dict): The remove-operation that will be checked
        """
        try:
            if not os.access(os.path.dirname(dop["symlink_name"]), os.W_OK):
                self._root_detected(dop, "remove links from",
                                    os.path.dirname(dop["symlink_name"]))
        except FileNotFoundError:
            raise FatalError(dop["symlink_name"] + " can't be checked " +
                             "for owner rights because it does not exist.")

    def _op_update_l(self, dop):
        """Checks if to be updated links are owned by other users than
        the current or will be moved to inaccessible directories.

        Args:
            dop (Dict): The update-operation that will be checked
        """
        name = dop["symlink2"]["name"]
        if dop["symlink1"]["uid"] != dop["symlink2"]["uid"] or \
                dop["symlink1"]["gid"] != dop["symlink2"]["gid"]:
            if dop["symlink2"]["uid"] != get_uid() or \
                    dop["symlink2"]["gid"] != get_gid():
                self._root_detected(dop, "change the owner of", name)
        if dop["symlink1"]["name"] != dop["symlink2"]["name"]:
            if not self._access(dop["symlink2"]["name"]):
                self._root_detected(dop, "create links in",
                                    os.path.dirname(name))
            if not self._access(dop["symlink1"]["name"]):
                self._root_detected(dop, "remove links from",
                                    os.path.dirname(name))
        if dop["symlink1"]["target"] != dop["symlink2"]["target"]:
            if not self._access(dop["symlink2"]["name"]):
                self._root_detected(dop, "change target of", name)

    @abstractmethod
    def _root_detected(self, dop, description, affected_file):
        """This method is called when requirement of root permission
        is detected.

        Args:
            dop (Dict): The operation that requires root permission
            description (str): A description of what the operation does that
                will require root permission
            affected_file (str): The file that the description refers to
        """
        pass


class SkipRootInterpreter(DetectRootInterpreter):
    """Skips all operatrions that would require root permission.

    Attributes:
        skipped (List): A list of all operations that will be skipped
        skipped_reasons (List): A list of tuples that counts how often a
            description occured
    """

    def __init__(self):
        super().__init__()
        self.skip = []
        self.skipped_reasons = {}

    def _root_detected(self, dop, description, affected_file):
        """Stores which operations needs to be skipped.

        Args:
            dop (Dict): The operation that will be skipped
            description (str): A description of what the operation does that
                will require root permission
            affected_file (str): Used to determine if description refers to
                a file or a directory
        """
        self.skip.append(dop)
        if os.path.isdir(affected_file):
            description += " protected directories"
        else:
            description += " protected files"
        if description not in self.skipped_reasons:
            self.skipped_reasons[description] = 1
        else:
            self.skipped_reasons[description] += 1

    def _op_fin(self, dop):
        """Remove all operations from difflog that are collected in self.skip

        Args:
            dop (Dict): Unused in this implementation
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
        logged (List): A list of tuples with (dop, description, affected_file)
            that stores which operations requiere root permission, which file
            or directory they affect and a description of what the operation
            would exactly requiere root permission for
    """

    def __init__(self):
        super().__init__()
        self.logged = []

    def _root_detected(self, dop, description, affected_file):
        """Logs and prints out the operation that needs root permission.

        Args:
            dop (Dict): Unused in this implementation
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
        of Dotmanager, but prepend it with "sudo".

        Args:
            dop (Dict): Unused in this implementation
        """
        if self.logged:
            if constants.ASKROOT:
                args = [sys.executable] + sys.argv
                os.execvp('sudo', args)
            else:
                raise UserError("You need to restart Dotmanager using 'sudo'" +
                                " or using the '--skiproot' option.")
