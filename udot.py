#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This is the main module. It implements the UberDot class and a short
startup script.

You can run this directly from the CLI with

.. code:: bash

    python ./udot.py <arguments>

or you can import UberDot for debugging and testing purposes."""

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

import argparse
import csv
import grp
import json
import logging
import os
import pwd
import shutil
import sys
import traceback

if os.getenv("COVERAGE_PROCESS_START"):
    # Restart coverage if spawned as a subprocess
    import coverage
    coverage.process_startup()

from uberdot import constants
from uberdot.interpreters import *
from uberdot.errors import CustomError
from uberdot.errors import FatalError
from uberdot.errors import PreconditionError
from uberdot.errors import UnkownError
from uberdot.errors import UserError
from uberdot.differencesolver import DiffSolver
from uberdot.differencesolver import DiffLog
from uberdot.utils import has_root_priveleges
from uberdot.utils import get_uid
from uberdot.utils import get_gid
from uberdot.utils import log_success
from uberdot.utils import log_warning
from uberdot.utils import normpath


class UberDot:
    """Bundles all functionality of uberdot.

    This includes things like parsing arguments, loading installed-files,
    printing information and executing profiles.

    Attributes:
        installed (dict): The installed-file that is used as a reference
        args (argparse): The parsed arguments
        owd (str): The old working directory uberdot was started from
    """

    def __init__(self):
        """Constructor

        Initializes attributes and changes the working directory to the
        directory where this module is stored."""
        # Initialise fields
        self.installed = {"@version": constants.VERSION}
        self.args = None
        # Change current working directory to the directory of this module
        self.owd = os.getcwd()
        newdir = os.path.abspath(sys.modules[__name__].__file__)
        os.chdir(os.path.dirname(newdir))

    def load_installed(self):
        """Reads the installed-file and parses it's content into
        :attr:`self.installed<UberDot.installed>`.

        Raises:
            :class:`~errors.PreconditionError`: uberdot and installed-file
                aren't version compatible.
        """
        try:
            self.installed = json.load(open(constants.INSTALLED_FILE))
        except FileNotFoundError:
            logger.debug("No installed profiles found.")
        # Check installed-file version
        if (int(self.installed["@version"].split("_")[1]) !=
                int(constants.VERSION.split("_")[1])):
            msg = "There was a change of the installed-file schema "
            msg += "with the last update. Please revert to version "
            msg += self.installed["@version"] + " and uninstall "
            msg += "all of your profiles before using this version."
            raise PreconditionError(msg)

    def parse_arguments(self, arguments=None):
        """Parses the commandline arguments. This function can parse a custom
        list of arguments, instead of ``sys.args``.

        Args:
            arguments (list): A list of arguments that will be parsed instead
                of ``sys.args``

        Raises:
            :class:`~errors.UserError`: One ore more arguments are invalid or
                used in an invalid combination.
        """
        global ch, formatter

        if arguments is None:
            arguments = sys.argv[1:]
        # Setup parser
        parser = CustomParser(add_help=False)
        # Options
        parser.add_argument("--config",
                            help="specify another config-file to use")
        parser.add_argument("--directory", help="set the default directory")
        parser.add_argument("-d", "--dryrun",
                            help="just simulate what would happen",
                            action="store_true")
        parser.add_argument("--dui",
                            help="use the DUI strategy for updating links",
                            action="store_true")
        parser.add_argument("-f", "--force",
                            help="overwrite existing files with links",
                            action="store_true")
        parser.add_argument("--info",
                            help="print everything but debug messages",
                            action="store_true")
        parser.add_argument("--log",
                            help="specify a file to log to")
        parser.add_argument("-m", "--makedirs",
                            help="create directories automatically if needed",
                            action="store_true")
        parser.add_argument("--option",
                            help="set options for profiles",
                            dest="opt_dict",
                            action=StoreDictKeyPair,
                            nargs="+",
                            metavar="KEY=VAL")
        parser.add_argument("--parent",
                            help="set the parent of the profiles you install")
        parser.add_argument("--plain",
                            help="print the internal DiffLog as plain json",
                            action="store_true")
        parser.add_argument("-p", "--print",
                            help="print what changes uberdot will do",
                            action="store_true")
        parser.add_argument("-q", "--quiet",
                            help="print nothing but errors",
                            action="store_true")
        parser.add_argument("--save",
                            help="specify another install-file to use",
                            default="default")
        parser.add_argument("--silent",
                            help="print absolute nothing",
                            action="store_true")
        parser.add_argument("--skiproot",
                            help="do nothing that requires root permissions",
                            action="store_true")
        parser.add_argument("--superforce",
                            help="overwrite blacklisted/protected files",
                            action="store_true")
        parser.add_argument("-v", "--verbose",
                            help="print stacktrace in case of error",
                            action="store_true")
        # Modes
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("-h", "--help",
                           help="show this help message and exit",
                           action="help")
        modes.add_argument("-i", "--install",
                           help="install and update (sub)profiles",
                           action="store_true")
        modes.add_argument("--debuginfo",
                           help="display internal values",
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

        # Options need some extra parsing for tags
        if self.args.opt_dict and "tags" in self.args.opt_dict:
            reader = csv.reader([self.args.opt_dict["tags"]])
            self.args.opt_dict["tags"] = next(reader)
        # And the directory was specified relative to the old working directory
        if self.args.directory:
            self.args.directory = os.path.join(self.owd, self.args.directory)
        # Like the path to the config file
        if self.args.config:
            self.args.config = os.path.join(self.owd, self.args.config)

        # Load constants for this installed-file
        constants.loadconfig(self.args.config, self.args.save)
        # Write back defaults from config for arguments that weren't set
        if not self.args.dui:
            self.args.dui = constants.DUISTRATEGY
        if not self.args.force:
            self.args.force = constants.FORCE
        if not self.args.makedirs:
            self.args.makedirs = constants.MAKEDIRS
        if not self.args.skiproot:
            self.args.skiproot = constants.SKIPROOT
        if not self.args.superforce:
            self.args.superforce = constants.SUPERFORCE
        if not self.args.directory:
            self.args.directory = constants.DIR_DEFAULT
        if not self.args.opt_dict:
            self.args.opt_dict = constants.DEFAULTS
        if not self.args.log and constants.LOGFILE:
            self.args.log = normpath(constants.LOGFILE)
        else:
            # Merge options provided by commandline with loaded defaults
            tmptags = self.args.opt_dict["tags"] + constants.DEFAULTS["tags"]
            self.args.opt_dict = {**constants.DEFAULTS, **self.args.opt_dict}
            self.args.opt_dict["tags"] = tmptags

        # Configure logger
        if self.args.silent:
            constants.LOGGINGLEVEL = "SILENT"
        if self.args.quiet:
            constants.LOGGINGLEVEL = "QUIET"
        if self.args.info:
            constants.LOGGINGLEVEL = "INFO"
        if self.args.verbose:
            constants.LOGGINGLEVEL = "VERBOSE"
        logging_level_mapping = {
            "SILENT": logging.CRITICAL,
            "QUIET": logging.WARNING,
            "INFO": logging.INFO,
            "VERBOSE": logging.DEBUG
        }
        try:
            logger.setLevel(logging_level_mapping[constants.LOGGINGLEVEL])
        except KeyError:
            msg = "Unkown logginglevel '" + constants.LOGGINGLEVEL + "'"
            raise UserError(msg)
        if self.args.log:
            ch = logging.FileHandler(os.path.join(self.owd, self.args.log))
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        # Check if settings are bad
        if constants.TARGET_FILES == constants.PROFILE_FILES:
            msg = "The directories for your profiles and for your dotfiles "
            msg += "are the same."
            raise UserError(msg)

        if not os.path.exists(constants.TARGET_FILES):
            msg = "The directory for your dotfiles '" + constants.TARGET_FILES
            msg += "' does not exist on this system."
            raise UserError(msg)

        if not os.path.exists(constants.PROFILE_FILES):
            msg = "The directory for your profiles '" + constants.PROFILE_FILES
            msg += "' does not exist on this system."
            raise UserError(msg)

        # Check if arguments are bad
        def args_depend(*args, need=[], omit=[], xor=False, msg=None):
            """Checks if argument dependencies are fullfilled.

            Args:
                *args (list): The argument names that depend on other arguments
                need (list): One of this need to be set if one of the arguments
                    is set
                omit (list): All of this need to be set if none of the
                    arguments are set
                xor (bool): Only one of the args is allowed to be set
                msg (str): An error message if dependecies aren't fullfilled. If
                    ommitted, it will be generated automatically
            Raises:
                UserError: The dependencies aren't fullfilled
            """
            def gen_msg():
                nonlocal msg
                if msg is not None:
                    return msg
                if need:
                    msg = "--" + "/--".join(args) + " need to be used with "
                    msg += "--" + "/--".join(need)
                if xor:
                    msg = "--" + "/--".join(args) + " can't be used together"
                if omit:
                    msg = "--" + ", --".join(omit) + " need to be specified "
                return msg
            # If at least one of the arguments is set
            set_args = [1 for arg in args if self.args.__dict__[arg]]
            if set_args:
                # we verify that at least one argument of need is set
                if need and not [1 for arg in need if self.args.__dict__[arg]]:
                    raise UserError(gen_msg())
                # or else only one is set if xor is set
                elif xor and len(set_args) > 1:
                    raise UserError(gen_msg())
            # No argument is set, so all args from "omit" need to be set
            elif omit and [x for x in omit if self.args.__dict__[x]] != omit:
                raise UserError(gen_msg())

        args_depend(
            "dryrun", "print", "plain",
            need=["install", "uninstall", "debuginfo"]
        )
        args_depend(
            "dryrun", "plain", "print",
            xor=True
        )
        args_depend(
            "silent", "quiet", "info", "verbose",
            xor=True
        )
        args_depend(
            "show", "version", "debuginfo",
            msg = "No Profile specified!!",
            omit=["profiles"]
        )
        args_depend(
            "parent", need=["install", "debuginfo"]
        )

    def execute_arguments(self):
        """Executes whatever was specified via commandline arguments."""
        if self.args.show:
            self.print_installed_profiles()
        elif self.args.version:
            print(constants.BOLD + "Version: " + constants.ENDC +
                  constants.VERSION)
        elif self.args.debuginfo:
            self.print_debuginfo()
        else:
            dfs = DiffSolver(self.installed, self.args)
            dfl = dfs.solve(self.args.install)
            if self.args.dui:
                dfl.run_interpreter(DUIStrategyInterpreter())
            if self.args.skiproot:
                dfl.run_interpreter(SkipRootInterpreter())
            if self.args.dryrun:
                self.dryrun(dfl)
            elif self.args.plain:
                dfl.run_interpreter(PlainPrintInterpreter())
            elif self.args.print:
                dfl.run_interpreter(PrintInterpreter())
            else:
                self.run(dfl)

    def print_debuginfo(self):
        """Print out internal values.

        This includes search paths of configs, loaded configs,
        parsed commandline arguments and settings.
        """

        def print_header(header):
            """Prints out a headline.

            Args:
                header (str): The header that will be printed
            """
            print(constants.BOLD + header + ":" + constants.ENDC)

        def print_value(name, val):
            """Prints out a value.

            Args:
                name (str): The name of the value that will be printed
                val (str): The value that will be printed
            """
            print(str("   " + name + ": ").ljust(32) + str(val))

        print_header("Config search paths")
        for cfg in constants.CONFIG_SEARCH_PATHS:
            print("   " + cfg)
        print_header("Loaded configs")
        for cfg in constants.CFG_FILES:
            print("   " + cfg)
        print_header("Arguments")
        print_value("DUISTRATEGY", self.args.dui)
        print_value("FORCE", self.args.force)
        print_value("LOGFILE", self.args.log)
        print_value("LOGGINGLEVEL", constants.LOGGINGLEVEL)
        print_value("MAKEDIRS", self.args.makedirs)
        print_value("SKIPROOT", self.args.skiproot)
        print_value("SUPERFORCE", self.args.superforce)
        print_header("Settings")
        print_value("ASKROOT", constants.ASKROOT)
        print_value("BACKUP_EXTENSION", constants.BACKUP_EXTENSION)
        print_value("DATA_DIR", constants.DATA_DIR)
        print_value("TAG_SEPARATOR", constants.TAG_SEPARATOR)
        print_value("HASH_SEPARATOR", constants.HASH_SEPARATOR)
        print_value("COLOR", constants.COLOR)
        print_value("DECRYPT_PWD", constants.DECRYPT_PWD)
        print_value("PROFILE_FILES", constants.PROFILE_FILES)
        print_value("TARGET_FILES", constants.TARGET_FILES)
        print_header("Command options")
        print_value("DEFAULTS['directory']", self.args.directory)
        print_value("DEFAULTS['extension']", self.args.opt_dict["extension"])
        print_value("DEFAULTS['name']", self.args.opt_dict["name"])
        print_value("DEFAULTS['optional']", self.args.opt_dict["optional"])
        print_value("DEFAULTS['owner']", self.args.opt_dict["owner"])
        print_value("DEFAULTS['permission']", self.args.opt_dict["permission"])
        print_value("DEFAULTS['prefix']", self.args.opt_dict["prefix"])
        print_value("DEFAULTS['replace']", self.args.opt_dict["replace"])
        print_value("DEFAULTS['replace_pattern']",
                    self.args.opt_dict["replace_pattern"])
        print_value("DEFAULTS['suffix']", self.args.opt_dict["suffix"])
        print_value("DEFAULTS['tags']", self.args.opt_dict["tags"])
        print_header("Internal values")
        print_value("INSTALLED_FILE", constants.INSTALLED_FILE)
        print_value("INSTALLED_FILE_BACKUP", constants.INSTALLED_FILE_BACKUP)

    def print_installed_profiles(self):
        """Print out the installed-file in a readable format.

        Prints only the profiles specified in the commandline arguments. If
        none are specified it prints all profiles of the installed-file."""
        if self.args.profiles:
            for profilename in self.args.profiles:
                if profilename in self.installed:
                    self.print_installed(self.installed[profilename])
                else:
                    log_warning("\nThe profile '" + profilename +
                                "' is not installed. Skipping...\n")
        else:
            for key in self.installed.keys():
                if key[0] != "@":
                    self.print_installed(self.installed[key])

    def print_installed(self, profile):
        """Prints a single installed profile.

        Args:
            profile (dict): The profile that will be printed
        """
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

    def run(self, difflog):
        """Performs checks on DiffLog and resolves it.

        Furthermore this function handles backups, converts exceptions into
        UnkownErrors and might replace the entire process when uberdot was
        started with insufficient permissions.

        Args:
            difflog (DiffLog): The DiffLog that will be resolved.

        Raises:
            :class:`~errors.UnkownError`: All exceptions that are no
                :class:`~errors.CustomError` and occured in the critical
                section will be converted to this error.
            :class:`~errors.CustomError`: Executed interpreters can and will
                raise all kinds of :class:`~errors.CustomError`.
        """
        # Run integration tests on difflog
        difflog.run_interpreter(
            CheckProfilesInterpreter(self.installed, self.args.parent)
        )
        tests = [
            CheckLinksInterpreter(self.installed),
            CheckLinkDirsInterpreter(self.args.makedirs),
            CheckLinkExistsInterpreter(self.args.force),
            CheckDynamicFilesInterpreter(False)
        ]
        difflog.run_interpreter(*tests)
        # Gain root if needed
        if not has_root_priveleges():
            difflog.run_interpreter(GainRootInterpreter())
        # Check blacklist not until now, because the user would need confirm it
        # twice if the programm is restarted with sudo
        difflog.run_interpreter(CheckLinkBlacklistInterpreter(self.args.superforce))
        # Now the critical part starts
        try:
            # Create Backup in case something wents wrong,
            # so the user can fix the mess we caused
            if os.path.isfile(constants.INSTALLED_FILE):
                shutil.copyfile(constants.INSTALLED_FILE,
                                constants.INSTALLED_FILE_BACKUP)
            # Execute all operations of the difflog and print them
            difflog.run_interpreter(ExecuteInterpreter(self.installed, self.args.force),
                                    PrintInterpreter())
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
            # Convert all exceptions that are not a CustomError in a
            # UnkownError to handle them in the outer pokemon handler
            raise UnkownError(err, msg)
        log_success("Finished successfully.")

    def dryrun(self, difflog):
        """Like `run()` but instead of resolving it it will be just printed out

        Args:
            difflog (DiffLog): The DiffLog that will be checked

        Raises:
            :class:`~errors.CustomError`: Executed interpreters can and will
                raise all kinds of :class:`~errors.CustomError`.
        """
        log_warning("This is just a dry-run! Nothing of this " +
                    "is actually happening.")
        difflog.run_interpreter(
            CheckProfilesInterpreter(self.installed, self.args.parent)
        )
        tests = [
            CheckLinksInterpreter(self.installed),
            CheckLinkBlacklistInterpreter(self.args.superforce),
            CheckLinkDirsInterpreter(self.args.makedirs),
            CheckLinkExistsInterpreter(self.args.force),
            CheckDynamicFilesInterpreter(True)
        ]
        difflog.run_interpreter(*tests)
        difflog.run_interpreter(RootNeededInterpreter())
        difflog.run_interpreter(PrintInterpreter())


class StoreDictKeyPair(argparse.Action):
    """Custom argparse.Action to parse an option dictionary from commandline"""

    def __call__(self, parser, namespace, values, option_string=None):
        """Splits a commandline argument at "=" and writes the splitted
        values into a dictionary."""
        opt_dict = {}
        for keyval in values:
            try:
                key, val = keyval.split("=")
            except ValueError:
                raise UserError("Expected KEY and VAL for --option," +
                                " but only found one.")
            opt_dict[key] = val
        setattr(namespace, self.dest, opt_dict)


class CustomParser(argparse.ArgumentParser):
    """Custom argument parser that raises an UserError instead of writing
    the error to stderr and exiting by itself."""
    def error(self, message):
        raise UserError(message)


def run_script(name):
    """Act like a script if we were invoked like a script.

    This is needed for coverage."""
    if name == "__main__":
        # Init the logger, further configuration is done when we parse the
        # commandline arguments
        logger = logging.getLogger("root")
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Create UberDot instance and parse arguments
        uber = UberDot()
        try:
            uber.parse_arguments()
        except CustomError as err:
            logger.error(err.message)
            sys.exit(err.EXITCODE)
        # Add the users profiles to the python path
        sys.path.append(constants.PROFILE_FILES)
        # Start everything in an exception handler
        try:
            if os.path.isfile(constants.INSTALLED_FILE_BACKUP):
                m = "I found a backup of your installed-file. It's most likely"
                m += " that the last execution of this tool failed. If you "
                m += "are certain that your installed-file is correct you can"
                m += " remove the backup and start this tool again."
                raise PreconditionError(m)
            uber.load_installed()
            uber.execute_arguments()
        except CustomError as err:
            # An error occured that we (more or less) expected.
            # Print error, a stacktrace and exit
            logger.debug(traceback.format_exc())
            if isinstance(err, FatalError):
                logger.critical(err.message)
            else:
                logger.error(err.message)
            sys.exit(err.EXITCODE)
        except Exception:
            # This works because all critical parts will catch also all
            # exceptions and convert them into a CustomError
            logger.error(traceback.format_exc())
            log_warning("The error above was unexpected. But it's fine," +
                        " I haven't done anything yet :)")
            sys.exit(100)
        finally:
            # Write installed-file back to json file
            try:
                with open(constants.INSTALLED_FILE, "w") as file:
                    file.write(json.dumps(uber.installed, indent=4))
                    file.flush()
                os.chown(constants.INSTALLED_FILE, get_uid(), get_gid())
            except Exception as err:
                unkw = UnkownError(err, "An unkown error occured when trying to " +
                                   "write all changes back to the installed-file")
                logger.error(unkw.message)

run_script(__name__)
