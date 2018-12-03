"""
This module contains all the different Interpreters.
Interpreters implement the behavior for all or a subset of DiffOperations.
This could be:
    - Checking if DiffOperations contradict each other
    - Printing a DiffOperation
    - Gaining root access if a DiffOperation needs them
    - Actually create links according to the DiffOperation
"""

import grp
import hashlib
import os
import pwd
import re
import sys
from shutil import copyfile
from subprocess import PIPE
from subprocess import Popen
from typing import Optional
from typing import Tuple
from bin import constants
from bin.errors import IntegrityError
from bin.errors import PreconditionError
from bin.errors import UnkownError
from bin.errors import UserError
from bin.errors import UserAbortion
from bin.errors import FatalError
from bin.types import InstalledLog
from bin.types import DiffLogData
from bin.types import DiffOperation
from bin.types import Path
from bin.utils import get_date_time_now
from bin.utils import get_dir_owner
from bin.utils import get_gid
from bin.utils import get_uid
from bin.utils import is_dynamic_file
from bin.utils import print_warning


class Interpreter():
    """Base-class for an interpreter"""
    def __init__(self):
        self.data = None
        self.use_interepreters = []

    def set_difflog_data(self, data: DiffLogData) -> None:
        """Sets the DiffLogData.
        Needed by Interpreters that alter the DiffLog"""
        self.data = data

    def call_operation(self, dop: DiffOperation) -> None:
        """Call the implemented behavior for this DiffOperation.
        This calls the function named like 'operation' with prefix '_op_'"""
        # Check if this interpreter has implemented the operation, then call
        attribute = getattr(self, "_op_" + dop["operation"], None)
        if callable(attribute):
            attribute(dop)


class PlainPrintI(Interpreter):
    """Prints add/remove/update-operation without any formating"""
    def __init__(self):
        super().__init__()
        self._op_add_p = self._op_remove_p = self._op_update_p = print
        self._op_add_l = self._op_remove_l = self._op_update_l = print


class PrintI(Interpreter):
    """Pretty-prints log messages and what a operations is going to do."""
    @staticmethod
    def _log_interpreter(dop: DiffOperation, message: str) -> None:
        print(constants.BOLD + "[" + dop["profile"] + "]: " +
              constants.NOBOLD + message)

    def _op_info(self, dop: DiffOperation) -> None:
        self._log_interpreter(dop, dop["message"])

    def _op_add_p(self, dop: DiffOperation) -> None:
        if dop["parent"] is not None:
            self._log_interpreter(dop, "Installing new profile as" +
                                  " subprofile of " + dop["parent"])
        else:
            self._log_interpreter(dop, "Installing new profile")

    def _op_remove_p(self, dop: DiffOperation) -> None:
        self._log_interpreter(dop, "Uninstalled profile")

    def _op_update_p(self, dop: DiffOperation) -> None:
        if "parent" in dop:
            if dop["parent"] is not None:
                self._log_interpreter(dop, "Changed parent to '" +
                                      dop["parent"] + "'")
            else:
                self._log_interpreter(dop, "Detached from parent." +
                                      " This is a root profile now.")
        self._log_interpreter(dop, "Profile updated")

    def _op_add_l(self, dop: DiffOperation) -> None:
        self._log_interpreter(dop, dop["symlink"]["name"] +
                              " was created and links to " +
                              dop["symlink"]["target"])

    def _op_remove_l(self, dop: DiffOperation) -> None:
        self._log_interpreter(dop, dop["symlink_name"] +
                              " was removed from the system.")

    def _op_update_l(self, dop: DiffOperation) -> None:
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


class DUIStrategyI(Interpreter):
    """Reorders DiffLog so linking won't be profile-wise but will do a
    Delete-Update-Insert for all links. Also removes log messages
    because without order they are not useful anymore"""
    def __init__(self):
        super().__init__()
        self.profile_deletes = []
        self.profile_updates = []
        self.profile_adds = []
        self.link_deletes = []
        self.link_updates = []
        self.link_adds = []

    def _op_add_p(self, dop: DiffOperation) -> None:
        self.profile_adds.append(dop)

    def _op_remove_p(self, dop: DiffOperation) -> None:
        self.profile_deletes.append(dop)

    def _op_update_p(self, dop: DiffOperation) -> None:
        self.profile_updates.append(dop)

    def _op_add_l(self, dop: DiffOperation) -> None:
        self.link_adds.append(dop)

    def _op_remove_l(self, dop: DiffOperation) -> None:
        self.link_deletes.append(dop)

    def _op_update_l(self, dop: DiffOperation) -> None:
        self.link_updates.append(dop)

    def _op_fin(self, dop: DiffOperation) -> None:
        merged_list = self.profile_deletes + self.profile_updates
        merged_list += self.profile_adds + self.link_deletes
        merged_list += self.link_updates + self.link_adds
        self.data.clear()
        for item in merged_list:
            self.data.append(item)


class CheckDynamicFilesI(Interpreter):
    """Checks if there are changes to a dynamic file and
    gives the user the oppoutunity to interact with them"""

    def __init__(self, dryrun: bool) -> None:
        self.dryrun = dryrun

    def _op_update_l(self, dop: DiffOperation) -> None:
        self.inspect_file(dop["symlink1"]["target"])

    def _op_remove_l(self, dop: DiffOperation) -> None:
        self.inspect_file(os.readlink(dop["symlink_name"]))

    def inspect_file(self, target: Path) -> None:
        """Checks if file is dynamic and has changed. """
        # Calculate new hash and get old has of file
        md5_calc = hashlib.md5(open(target, "rb").read()).hexdigest()
        md5_old = os.path.basename(target)[-32:]
        # Check for changes
        if is_dynamic_file(target) and md5_calc != md5_old:
            print_warning(f"You made changes to '{target}'. Those changes " +
                          "will be lost, if you don't write them back to " +
                          "the original file.")
            self.user_interaction(target)

    def user_interaction(self, target: Path) -> None:
        """Gives the user the ability to interact with a changed file"""
        target_bak = target + "." + constants.BACKUP_EXTENSION
        done = False
        while not done:
            inp = input("[A]bort / [I]gnore / Show [D]iff " +
                        "/ Create [P]atch / [U]ndo changes: ")
            if inp == "A":
                raise UserAbortion
            elif inp == "I":
                done = True
            elif inp == "D":
                process = Popen(["diff", "--color=auto", target_bak, target])
                process.communicate()
            elif inp == "P":
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
                    msg = f"Could not write patch file '{patch_file}'."
                    raise PreconditionError(msg)
            elif inp == "U":
                if self.dryrun:
                    print("This does nothing this time since " +
                          "this is just a dry-run")
                else:
                    copyfile(target_bak, target)
                done = True
            else:
                print_warning("Invalid option")


class CheckLinksI(Interpreter):
    """Checks for conflicts between all links
    (duplicates, multiple targets, overwrites, etc)"""
    def __init__(self, installed: InstalledLog):
        super().__init__()
        # Setup linklist to store/lookup which links are modified
        self.linklist = []
        for key, profile in installed.items():
            if key[0] != "@":
                for link in profile["links"]:
                    self.linklist.append((link["name"], profile["name"], True))

    def _op_add_l(self, dop: DiffOperation) -> None:
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

    def _op_remove_l(self, dop: DiffOperation) -> None:
        count = 0
        for item in self.linklist:
            if item[0] == dop["symlink_name"]:
                break
            count += 1
        self.linklist.pop(count)


class CheckLinkBlacklistI(Interpreter):
    """Checks if links are on blacklist"""
    def __init__(self, superforce: bool) -> None:
        super().__init__()
        # Load blacklist
        self.superforce = superforce
        with open("data/black.list", "r") as file:
            self.blacklist = file.readlines()
        self.blacklist = [entry.strip() for entry in self.blacklist]

    def check_blacklist(self, symlink_name: Path) -> None:
        """Checks if the symlink matches on a pattern in the blacklist"""
        for entry in self.blacklist:
            if re.search(entry, symlink_name):
                print_warning("You are trying to overwrite '" + symlink_name +
                              "' which is blacklisted. It is considered " +
                              "dangerous to overwrite those files!")
                if self.superforce:
                    print_warning("Are you sure that you want to overwrite " +
                                  "a blacklisted file?")
                    confirmation = input("Type \"YES\" to confirm or " +
                                         "anything else to cancel: ")
                    if confirmation != "YES":
                        raise UserError("Canceled by user")
                else:
                    print_warning("If you really want to modify this file" +
                                  " you can use the --superforce flag to" +
                                  " ignore the blacklist.")
                    raise IntegrityError("Won't overwrite blacklisted file!")

    def _op_update_l(self, dop: DiffOperation) -> None:
        self.check_blacklist(dop["symlink1"]["name"])
        self.check_blacklist(dop["symlink2"]["name"])

    def _op_remove_l(self, dop: DiffOperation) -> None:
        self.check_blacklist(dop["symlink_name"])

    def _op_add_l(self, dop: DiffOperation) -> None:
        self.check_blacklist(dop["symlink"]["name"])


class CheckLinkDirsI(Interpreter):
    """Checks if directories need to be created"""
    def __init__(self, makedirs: bool) -> None:
        super().__init__()
        self.makedirs = makedirs

    def _op_add_l(self, dop: DiffOperation) -> None:
        self.check_dirname(os.path.dirname(dop["symlink"]["name"]))

    def _op_update_l(self, dop: DiffOperation) -> None:
        self.check_dirname(os.path.dirname(dop["symlink2"]["name"]))

    def check_dirname(self, dirname: str) -> None:
        """Checks if the if the directory is already created"""
        if not self.makedirs:
            if not os.path.isdir(dirname):
                msg = "The directory '" + dirname + "/' needs to be created "
                msg += "in order to perform this action, but "
                msg += "--makedirs is not set"
                raise PreconditionError(msg)


class CheckLinkExistsI(Interpreter):
    """Checks if links of installed-file exist in the filesystem"""
    def __init__(self, force: bool) -> None:
        super().__init__()
        self.force = force
        self.removed_links = []

    def _op_remove_l(self, dop: DiffOperation) -> None:
        if not os.path.lexists(dop["symlink_name"]):
            msg = "'" + dop["symlink_name"] + "' can not be removed because"
            msg += " removed because it does not exist on your filesystem."
            msg += " Check your installed file!"
            raise PreconditionError(msg)
        self.removed_links.append(dop["symlink_name"])

    @staticmethod
    def _op_update_l(dop: DiffOperation) -> None:
        if not os.path.lexists(dop["symlink1"]["name"]):
            msg = "'" + dop["symlink1"]["name"] + "' can not be updated"
            msg += " because it does not exist on your filesystem."
            msg += " Check your installed file!"
            raise PreconditionError(msg)
        if (dop["symlink1"]["name"] != dop["symlink2"]["name"]
                and os.path.lexists(dop["symlink2"]["name"])):
            msg = "'" + dop["symlink1"]["name"] + "' can not be moved to '"
            msg += dop["symlink2"]["name"] + "' because it already exist on"
            msg += " your filesystem and would be overwritten."
            raise PreconditionError(msg)

    def _op_add_l(self, dop: DiffOperation) -> None:
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


class CheckProfilesI(Interpreter):
    """Checks if profiles can be installed together, protects against
    duplicates and overwrites"""
    def __init__(self, installed: InstalledLog, parent_arg: str = None):
        super().__init__()
        self.parent_arg = parent_arg
        self.profile_list = []
        for key, profile in installed.items():
            if key[0] != "@":
                self.profile_list.append(
                    (profile["name"],
                     profile["parent"] if "parent" in profile else None, True))

    def get_known(self, name: str,
                  is_installed: bool) -> Optional[Tuple[str, str, bool]]:
        """Return if parent is already known as installed
        or a to-be-linked profile"""
        for p_name, p_parent, p_installed in self.profile_list:
            if name == p_name and p_installed == is_installed:
                return (p_name, p_parent, p_installed)
        return None

    def _op_add_p(self, dop: DiffOperation) -> None:
        known = self.get_known(dop["profile"], False)
        if known is not None:
            if known[1] is not None:
                msg = "The profile '" + dop["profile"]
                msg += "' would be already subprofile of '" + known[1] + "'."
                raise IntegrityError(msg)
            else:
                msg = "The profile '" + dop["profile"]
                msg += "' would be already installed."
                raise IntegrityError(msg)
        if self.get_known(dop["profile"], True) is not None:
            raise FatalError("addP-operation found where" +
                             " update_p-operation was expected")
        self.profile_list.append(
            (dop["profile"], dop["parent"] if "parent" in dop else None, False)
        )

    def _op_update_p(self, dop: DiffOperation) -> None:
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


class ExecuteI(Interpreter):
    """This interpreter actually executes the operations from the DiffLog.
    It can create/delete links in the filesystem and modify the InstalledLog"""
    def __init__(self, installed: InstalledLog, force: bool) -> None:
        super().__init__()
        self.installed = installed
        self.installed["@version"] = constants.VERSION  # Update version number
        self.force = force

    def _op_add_p(self, dop: DiffOperation) -> None:
        new_profile = {}
        new_profile["name"] = dop["profile"]
        new_profile["links"] = []
        new_profile["installed"] = new_profile["updated"] = get_date_time_now()
        if dop["parent"] is not None:
            new_profile["parent"] = dop["parent"]
        self.installed[new_profile["name"]] = new_profile

    def _op_remove_p(self, dop: DiffOperation) -> None:
        del self.installed[dop["profile"]]

    def _op_update_p(self, dop: DiffOperation) -> None:
        if "parent" in dop:
            if dop["parent"] is not None:
                self.installed[dop["profile"]]["parent"] = dop["parent"]
            elif "parent" in self.installed[dop["profile"]]:
                del self.installed[dop["profile"]]["parent"]
        self.installed[dop["profile"]]["updated"] = get_date_time_now()

    def _op_add_l(self, dop: DiffOperation) -> None:
        self.__create_symlink(dop["symlink"]["name"],
                              dop["symlink"]["target"],
                              dop["symlink"]["uid"],
                              dop["symlink"]["gid"],
                              dop["symlink"]["permission"])
        self.installed[dop["profile"]]["links"].append(dop["symlink"])

    def _op_remove_l(self, dop: DiffOperation) -> None:
        os.unlink(dop["symlink_name"])
        for link in self.installed[dop["profile"]]["links"]:
            if link["name"] == dop["symlink_name"]:
                self.installed[dop["profile"]]["links"].remove(link)

    def _op_update_l(self, dop: DiffOperation) -> None:
        os.unlink(dop["symlink1"]["name"])
        self.__create_symlink(dop["symlink2"]["name"],
                              dop["symlink2"]["target"],
                              dop["symlink2"]["uid"],
                              dop["symlink2"]["gid"],
                              dop["symlink2"]["permission"])
        self.installed[dop["profile"]]["links"].remove(dop["symlink1"])
        self.installed[dop["profile"]]["links"].append(dop["symlink2"])

    def __create_symlink(self, name: Path, target: Path,
                         uid: int, gid: int, permission: int) -> None:
        """Create a symlink in the filesystem"""
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
    def _makedirs(filename: Path) -> None:
        """Custom makedirs that keeps fixes the owner of the directory"""
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


class RootNeededI(Interpreter):
    """Checks if root permission is needed to perform the operations"""
    def __init__(self):
        super().__init__()
        self.root_needed = False
        self.logged = []

    def _access(self, path: Path) -> bool:
        """Checks if we have write access for a given path.
        Because the path does not need to be existent at this point,
        this function goes the full directory tree upwards until it finds
        a directory that we have write accesss to"""
        if not path or path == "/":
            return False
        dirname = os.path.dirname(path)
        if os.access(dirname, os.W_OK):
            return True
        return self._access(dirname)

    def _op_add_l(self, dop: DiffOperation) -> None:
        name = dop["symlink"]["name"]
        uid, gid = get_dir_owner(name)
        if dop["symlink"]["uid"] != uid or dop["symlink"]["gid"] != gid:
            self._root_needed("change owner of", name)
        elif not self._access(name):
            self._root_needed("create links in", os.path.dirname(name))

    def _op_remove_l(self, dop: DiffOperation) -> None:
        try:
            if not os.access(os.path.dirname(dop["symlink_name"]), os.W_OK):
                self._root_needed("remove links from",
                                  os.path.dirname(dop["symlink_name"]))
        except FileNotFoundError:
            raise FatalError(dop["symlink_name"] + " can't be checked " +
                             "for owner rights because it does not exist.")

    def _op_update_l(self, dop: DiffOperation) -> None:
        if dop["symlink1"]["uid"] != dop["symlink2"]["uid"] or \
                dop["symlink1"]["gid"] != dop["symlink2"]["gid"]:
            name = dop["symlink2"]["name"]
            if dop["symlink2"]["uid"] != get_uid() or \
                    dop["symlink2"]["gid"] != get_gid():
                self._root_needed("change the owner of", name)
        if dop["symlink1"]["name"] != dop["symlink2"]["name"]:
            if not self._access(dop["symlink2"]["name"]):
                self._root_needed("create links in", os.path.dirname(name))
            if not self._access(dop["symlink1"]["name"]):
                self._root_needed("remove links from", os.path.dirname(name))

    def _root_needed(self, operation: str, filename: Path) -> None:
        self.root_needed = True
        if (operation, filename) not in self.logged:
            print_warning("You will need to give me root permission to " +
                          operation + " '" + filename + "'.")
            self.logged.append((operation, filename))


class GainRootI(RootNeededI):
    """If root permission is needed to perform the operations,
    this interpreter restarts the process with sudo"""
    def _op_fin(self, dop: DiffOperation) -> None:
        if self.root_needed:
            print(constants.FAIL + constants.BOLD +
                  "I HOPE YOU KNOW WHAT YOU DO!!" + constants.ENDC)
            args = [sys.executable] + sys.argv
            os.execvp('sudo', args)
