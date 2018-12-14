#!/usr/bin/env python3
"""Main module. Implements DotManager and a short startup script.
Run this directly from the CLI or import DotManager for debugging"""

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

import argparse
import csv
import grp
import json
import os
import pwd
import shutil
import sys
import traceback
from typing import List
from bin import constants
from bin.interpreters import CheckDynamicFilesI
from bin.interpreters import CheckLinkBlacklistI
from bin.interpreters import CheckLinkDirsI
from bin.interpreters import CheckLinkExistsI
from bin.interpreters import CheckLinksI
from bin.interpreters import CheckProfilesI
from bin.interpreters import DUIStrategyI
from bin.interpreters import ExecuteI
from bin.interpreters import GainRootI
from bin.interpreters import PlainPrintI
from bin.interpreters import PrintI
from bin.interpreters import RootNeededI
from bin.errors import CustomError
from bin.errors import PreconditionError
from bin.errors import UnkownError
from bin.errors import UserError
from bin.differencesolver import DiffSolver
from bin.differencelog import DiffLog
from bin.types import InstalledProfile
from bin.types import ProfileResult
from bin.utils import has_root_priveleges
from bin.utils import get_uid
from bin.utils import get_gid
from bin.utils import print_success
from bin.utils import print_warning


class DotManager:
    """Main class. Parses arguments, generates DiffLog and calls DiffOperations
    on DiffLog according to the parsed arguments."""

    def __init__(self):
        # Fields
        self.installed = {"@version": constants.VERSION}
        self.args = None
        # Change current working directory to the directory of this module
        self.owd = os.getcwd()
        os.chdir(os.path.dirname(sys.modules[__name__].__file__))

    def load_installed(self) -> None:
        """Reads Installed-File and parses it's InstallationLog
        into self.installed"""
        try:
            self.installed = json.load(open(constants.INSTALLED_FILE))
        except FileNotFoundError:
            print("No installed profiles found.")
        # Check installed-file version
        if (int(self.installed["@version"].split("_")[1]) !=
                int(constants.VERSION.split("_")[1])):
            msg = "There was a change of the installed-file schema "
            msg += "with the last update. Please revert to version "
            msg += self.installed["@version"] + " and uninstall "
            msg += "all of your profiles before using this version."
            raise PreconditionError(msg)

    def parse_arguments(self, arguments: List[str] = None) -> None:
        """Creates an ArgumentParser and parses sys.args into self.args"""
        if arguments is None:
            arguments = sys.argv[1:]
        # Setup parser
        parser = argparse.ArgumentParser(add_help=False)
        # Options
        parser.add_argument("--directory", help="set the default directory")
        parser.add_argument("-d", "--dryrun",
                            help="just simulate what would happen",
                            action="store_true")
        parser.add_argument("--dui",
                            help="use the DUI strategy for updating links",
                            action="store_true",
                            default=constants.DUISTRATEGY)
        parser.add_argument("-f", "--force",
                            help="overwrite existing files with links",
                            action="store_true",
                            default=constants.FORCE)
        parser.add_argument("-m", "--makedirs",
                            help="create directories automatically if needed",
                            action="store_true",
                            default=constants.MAKEDIRS)
        parser.add_argument("--option",
                            help="set options for profiles",
                            dest="opt_dict",
                            action=StoreDictKeyPair,
                            nargs="+",
                            metavar="KEY=VAL")
        parser.add_argument("--parent",
                            help="set the parent of the profiles you install",
                            default=None)
        parser.add_argument("--plain",
                            help="print the internal DiffLog as plain json",
                            action="store_true")
        parser.add_argument("-p", "--print",
                            help="print what changes dotmanager will do",
                            action="store_true")
        parser.add_argument("--save",
                            help="specify another install-file to use",
                            default="default")
        parser.add_argument("--superforce",
                            help="overwrite blacklisted/protected files",
                            action="store_true")
        parser.add_argument("-v", "--verbose",
                            help="print stacktrace in case of error",
                            action="store_true",
                            default=constants.VERBOSE)
        # Modes
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("-h", "--help",
                           help="show this help message and exit",
                           action="help")
        modes.add_argument("-i", "--install",
                           help="install and update (sub)profiles",
                           action="store_true")
        modes.add_argument("-u", "--uninstall",
                           help="uninstall (sub)profiles",
                           action="store_true")
        modes.add_argument("-s", "--show",
                           help="show infos about installed profiles",
                           action="store_true")
        modes.add_argument("--version",
                           help="print version number",
                           action="store_true")
        # Profile list
        parser.add_argument("profiles",
                            help="list of root profiles",
                            nargs="*")
        # Read arguments
        try:
            self.args = parser.parse_args(arguments)
        except argparse.ArgumentError as err:
            raise UserError(err.message)
        if self.args.opt_dict and "tags" in self.args.opt_dict:
            reader = csv.reader([self.args.opt_dict["tags"]])
            self.args.opt_dict["tags"] = next(reader)
        if self.args.directory:
            self.args.directory = os.path.join(self.owd, self.args.directory)
        # Check if arguments are bad
        if (not (self.args.show or self.args.version)
                and not self.args.profiles):
            raise UserError("No Profile specified!!")
        if ((self.args.dryrun or self.args.force or self.args.plain or
             self.args.dui) and not
                (self.args.install or self.args.uninstall)):
            raise UserError("-d/-f/-p/--dui needs to be used with -i or -u")
        if self.args.parent and not self.args.install:
            raise UserError("--parent needs to be used with -i")
        # Load constants for this installed-file
        constants.load_constants(self.args.save)

    def execute_arguments(self) -> None:
        """Executes whatever was specified via commandline arguments"""
        if self.args.show:
            self.print_installed_profiles()
        elif self.args.version:
            print(constants.BOLD + "Version: " + constants.ENDC +
                  constants.VERSION)
        else:
            dfs = DiffSolver(self.installed, self.args)
            dfl = dfs.solve(self.args.install)
            if self.args.dui:
                dfl.run_interpreter(DUIStrategyI())
            if self.args.dryrun:
                self.dryrun(dfl)
            elif self.args.plain:
                dfl.run_interpreter(PlainPrintI())
            elif self.args.print:
                dfl.run_interpreter(PrintI())
            else:
                self.run(dfl)

    def print_installed_profiles(self) -> None:
        """Shows only the profiles specified.
        If none are specified shows all."""
        if self.args.profiles:
            for profilename in self.args.profiles:
                if profilename in self.installed:
                    self.print_installed(self.installed[profilename])
                else:
                    print_warning("\nThe profile '" + profilename +
                                  "' is not installed. Skipping...\n")
        else:
            for key in self.installed.keys():
                if key[0] != "@":
                    self.print_installed(self.installed[key])

    def run(self, difflog: DiffLog) -> None:
        """This runs Checks then executes DiffOperations while
        pretty printing the DiffLog"""
        # Run integration tests on difflog
        difflog.run_interpreter(
            CheckProfilesI(self.installed, self.args.parent)
        )
        tests = [
            CheckLinksI(self.installed),
            CheckLinkDirsI(self.args.makedirs),
            CheckLinkExistsI(self.args.force),
            CheckDynamicFilesI(False)
        ]
        difflog.run_interpreter(*tests)
        # Gain root if needed
        if not has_root_priveleges():
            difflog.run_interpreter(GainRootI())
        # Check blacklist not until now, because the user would need confirm it
        # twice if the programm is restarted with sudo
        difflog.run_interpreter(CheckLinkBlacklistI(self.args.superforce))
        # Now the critical part starts
        try:
            # Create Backup in case something wents wrong,
            # so the user can fix the mess we caused
            if os.path.isfile(constants.INSTALLED_FILE):
                shutil.copyfile(constants.INSTALLED_FILE,
                                constants.INSTALLED_FILE_BACKUP)
            # Execute all operations of the difflog and print them
            difflog.run_interpreter(ExecuteI(self.installed, self.args.force),
                                    PrintI())
            # Remove Backup
            if os.path.isfile(constants.INSTALLED_FILE_BACKUP):
                os.remove(constants.INSTALLED_FILE_BACKUP)
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during linking/unlinking. Some "
            msg += "links or your installed-file may be corrupted! Check the "
            msg += "backup of your installed-file to resolve all possible "
            msg += "issues before you proceed to use this tool!"
            raise UnkownError(err, msg) from err
        print_success("Finished succesfully.")

    @staticmethod
    def print_installed(profile: InstalledProfile) -> None:
        """Prints a currently InstalledProfile"""
        print(constants.BOLD + profile["name"] + ":" + constants.ENDC)
        print("  Installed: " + profile["installed"])
        print("  Updated: " + profile["updated"])
        if "parent" in profile:
            print("  Subprofile of: " + profile["parent"])
        if "profiles" in profile:
            print("  Has Subprofiles: " + ", ".join(
                [s["name"] for s in profile["profiles"]]
            ))
        if profile["links"]:
            print("  Links:")
        for symlink in profile["links"]:
            print("    " + symlink["name"] + "  →  " + symlink["target"])
            user = pwd.getpwuid(symlink["uid"])[0]
            group = grp.getgrgid(symlink["gid"])[0]
            print("       Owner: " + user + ":" + group +
                  "   Permission: " + str(symlink["permission"]) +
                  "   Updated: " + symlink["date"])

    def dryrun(self, difflog: DiffLog) -> None:
        """Runs Checks and pretty prints the DiffLog"""
        print_warning("This is just a dry-run! Nothing of this " +
                      "is actually happening.")
        difflog.run_interpreter(
            CheckProfilesI(self.installed, self.args.parent)
        )
        tests = [
            CheckLinksI(self.installed),
            CheckLinkBlacklistI(self.args.superforce),
            CheckLinkDirsI(self.args.makedirs),
            CheckLinkExistsI(self.args.force),
            CheckDynamicFilesI(True)
        ]
        difflog.run_interpreter(*tests)
        difflog.run_interpreter(RootNeededI())
        difflog.run_interpreter(PrintI())


class StoreDictKeyPair(argparse.Action):
    """Used to parse an option dict from commandline"""
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        self._nargs = nargs
        super(StoreDictKeyPair, self).__init__(
            option_strings, dest, nargs=nargs, **kwargs
        )

    def __call__(self, parser, namespace, values, option_string=None):
        opt_dict = {}
        for keyval in values:
            try:
                key, val = keyval.split("=")
            except ValueError:
                raise UserError("Expected KEY and VAL for --option," +
                                " but only found one.")
            opt_dict[key] = val
        setattr(namespace, self.dest, opt_dict)


if __name__ == "__main__":
    # Create DotManager and parse arguments
    dotm = DotManager()
    try:
        dotm.parse_arguments()
    except CustomError as err:
        print(err.message)
        sys.exit(err.exitcode)
    # Add the profiles to the python path
    sys.path.append(constants.PROFILE_FILES)
    # Start everything in an exception handler
    try:
        if os.path.isfile(constants.INSTALLED_FILE_BACKUP):
            raise PreconditionError("I found a backup of your installed-" +
                                    "file. It's most likely that the last " +
                                    "execution of this tool failed. If you " +
                                    "are certain that your installed-file " +
                                    "is correct you can remove the backup " +
                                    "and start this tool again.")
        else:
            dotm.load_installed()
            dotm.execute_arguments()
    except CustomError as err:
        # An error occured that we (more or less) expected.
        # Print error, maybe a stacktrace and exit
        if dotm.args.verbose:
            traceback.print_exc()
        print(err.message)
        sys.exit(err.exitcode)
    except Exception:
        # This works because all critical parts will catch also all
        # exceptions and convert them into a CustomError
        traceback.print_exc()
        print("")
        print_warning("The error above was unexpected. But it's fine," +
                      " I haven't done anything yet :)")
        sys.exit(100)
    finally:
        # Write installed back to json file
        try:
            with open(constants.INSTALLED_FILE, "w") as file:
                file.write(json.dumps(dotm.installed, indent=4))
            os.chown(constants.INSTALLED_FILE, get_uid(), get_gid())
        except Exception as err:
            raise UnkownError(err, "An unkown error occured when trying to " +
                              "write all changes back to the installed-file")
