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

from uberdot.constants import Const
from uberdot.interpreters import *
from uberdot.errors import CustomError
from uberdot.errors import FatalError
from uberdot.errors import PreconditionError
from uberdot.errors import UnkownError
from uberdot.errors import UserError
from uberdot.differencesolver import UpdateDiffSolver
from uberdot.differencesolver import UninstallDiffSolver
from uberdot.differencesolver import DiffLog
from uberdot.utils import has_root_priveleges
from uberdot.utils import get_uid
from uberdot.utils import get_gid
from uberdot.utils import import_profile_class
from uberdot.utils import log_debug
from uberdot.utils import log_error
from uberdot.utils import log_success
from uberdot.utils import log_warning
from uberdot.utils import normpath


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

const = None

class UberDot:
    """Bundles all functionality of uberdot.

    This includes things like parsing arguments, loading installed-files,
    printing information and executing profiles.

    Attributes:
        installed (dict): The installed-file that is used as a reference
        profiles (list): A list of the to be installed/updated profiles
        args (argparse): The parsed arguments
        owd (str): The old working directory uberdot was started from
    """

    def __init__(self):
        """Constructor.

        Initializes attributes and changes the working directory to the
        directory where this module is stored."""
        # Initialise fields
        self.installed = {"@version": const.version}
        self.args = None
        self.profiles = []
        # Change current working directory to the directory of this module
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
            self.installed = json.load(open(const.installed_file))
        except FileNotFoundError:
            log_debug("No installed profiles found.")
        # Check installed-file version
        if (int(self.installed["@version"].split("_")[1]) !=
                int(const.version.split("_")[1])):
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
        if arguments is None:
            arguments = sys.argv[1:]
        # Setup parser
        parser = CustomParser()
        subparsers = parser.add_subparsers(
            parser_class=CustomParser,
            dest="mode"
        )
        parser_profiles = CustomParser(add_help=False)
        parser_profiles.add_argument("profiles",
                                     help="do this only for this list of root profiles",
                                     nargs="*")
        # Setup top level arguments
        parser.add_argument("--config",
                            help="specify another config-file to use")
        parser.add_argument("--debuginfo",
                            help="show loaded settings and internal values")
        group_log_level = parser.add_mutually_exclusive_group()
        group_log_level.add_argument("-v", "--verbose",
                            help="print debug messages and tracebacks",
                            action="store_true")
        group_log_level.add_argument("--info",
                            help="print everything but debug messages",
                            action="store_true")
        group_log_level.add_argument("-q", "--quiet",
                            help="print nothing but errors",
                            action="store_true")
        group_log_level.add_argument("--silent",
                            help="print absolute nothing",
                            action="store_true")
        parser.add_argument("--log",
                            help="specify a file to log to")
        parser.add_argument("--save",
                            help="specify another install-file to use",
                            default="default")
        # Setup mode show arguments
        help_text = "display various information about installed profiles"
        parser_show = subparsers.add_parser(
            "show",
            parents=[parser_profiles],
            description=help_text,
            help=help_text
        )
        parser_show.add_argument("-l", "--links",
                                 help="show installed links",
                                 action="store_true")
        # TODO: profiles can not be there twice
        parser_show.add_argument("-p", "--profiles",
                                 help="show installed profiles",
                                 action="store_true")
        parser_show.add_argument("-m", "--meta",
                                 help="display meta information about profiles and/or links",
                                 action="store_true")
        # Setup arguments that are used in both update and remove
        parser_run = CustomParser(add_help=False)
        group_run_mode = parser_run.add_mutually_exclusive_group()
        group_run_mode.add_argument("-d", "--dryrun",
                                    help="just simulate what would happen",
                                    action="store_true")
        group_run_mode.add_argument("--plain",
                                    help="print the internal DiffLog as plain json",
                                    action="store_true")
        group_run_mode.add_argument("-p", "--print",
                                    help="print what changes uberdot will do",
                                    action="store_true")
        parser_run.add_argument("-f", "--force",
                                help="overwrite existing files",
                                action="store_true")
        parser_run.add_argument("--skiproot",
                                help="do nothing that requires root permissions",
                                action="store_true")
        parser_run.add_argument("--superforce",
                                help="overwrite blacklisted/protected files",
                                action="store_true")
        parser_run.add_argument("--skipafter",
                            help="do not execute events after linking",
                            action="store_true")
        parser_run.add_argument("--skipbefore",
                            help="do not execute events before linking",
                            action="store_true")
        parser_run.add_argument("--skipevents",
                            help="do not execute any events",
                            action="store_true")
        # Setup mode update arguments
        help_text="install new or update already installed profiles"
        parser_update = subparsers.add_parser(
            "update",
            parents=[parser_run, parser_profiles],
            description=help_text,
            help=help_text
        )
        parser_update.add_argument("--dui",
                                   help="use the DUI strategy for updating links",
                                   action="store_true")
        parser_update.add_argument("--directory", help="set the default directory")
        parser_update.add_argument("-m", "--makedirs",
                                   help="create directories automatically if needed",
                                   action="store_true")
        parser_update.add_argument("--option",
                                   help="set options for profiles",
                                   dest="opt_dict",
                                   action=StoreDictKeyPair,
                                   nargs="+",
                                   metavar="KEY=VAL")
        parser_update.add_argument("--parent",
                                   help="set the parent of the profiles you install")
        # Setup mode remove arguments
        help_text="remove already installed profiles"
        parser_remove = subparsers.add_parser(
            "remove",
            parents=[parser_run, parser_profiles],
            description=help_text,
            help=help_text
        )
        # Setup mode find arguments
        help_text="helpers to search profiles and dotfiles manually"
        parser_find = subparsers.add_parser(
            "find",
            description=help_text,
            help=help_text
        )
        # Setup mode version arguments
        help_text="show version number"
        parser_version = subparsers.add_parser(
            "version",
            description=help_text,
            help=help_text
        )
        # TODO: finish parser
        # TODO: add new args to const

        # Read arguments
        try:
            args = parser.parse_args(arguments)
        except argparse.ArgumentError as err:
            raise UserError(err.message)

        # Load args and configs into const
        const.load(args)

        if args.debuginfo:
            # At this point everything is loaded, so we print debuginfo
            # immediatly so no exception that might occurs later due to
            # inproper configuration won't "shadow" this
            self.print_debuginfo()
            sys.exit(0)

        # Configure logger
        logging_level_mapping = {
            "SILENT": logging.CRITICAL,
            "QUIET": logging.WARNING,
            "INFO": logging.INFO,
            "VERBOSE": logging.DEBUG
        }
        try:
            logger.setLevel(logging_level_mapping[const.logginglevel])
        except KeyError:
            msg = "Unkown logginglevel '" + const.logginglevel + "'"
            raise UserError(msg)
        if const.logfile:
            ch = logging.FileHandler(const.logfile)
            ch.setLevel(logging.DEBUG)
            form = '[%(asctime)s] - %(levelname)s - %(message)s'
            formatter = logging.Formatter(form)
            ch.setFormatter(formatter)
            logger.addHandler(ch)

    def check_arguments(self):
        """Checks if parsed arguments/settings are bad or incompatible to
        each other. If not, it raises an UserError."""
        # Check if settings are bad
        if not const.target_files:
            raise UserError("You need to set target_files in your config")
        if not const.profile_files:
            raise UserError("You need to set profile_files in your config")
        if const.target_files == const.profile_files:
            msg = "The directories for your profiles and for your dotfiles "
            msg += "are the same."
            raise UserError(msg)
        if not os.path.exists(const.target_files):
            msg = "The directory for your dotfiles '" + const.target_files
            msg += "' does not exist on this system."
            raise UserError(msg)
        if not os.path.exists(const.profile_files):
            msg = "The directory for your profiles '" + const.profile_files
            msg += "' does not exist on this system."
            raise UserError(msg)

    def execute_arguments(self):
        """Executes whatever was specified via commandline arguments."""
        # TODO: remove the use of self.args
        if self.args.show:
            self.print_installed_profiles()
        elif self.args.version:
            print(const.col_bold + "Version: " + const.col_endc +
                  const.version)
        elif self.args.debuginfo:
            self.print_debuginfo()
        else:
            # The above are modes that just print stuff, but here we
            # have to actually do something:
            # 1. Decide how to solve the differences
            if self.args.uninstall:
                dfs = UninstallDiffSolver(self.installed, self.args.profiles)
            elif self.args.install:
                self.execute_profiles()
                profile_results = [p.result for p in self.profiles]
                dfs = UpdateDiffSolver(self.installed,
                                       profile_results,
                                       self.args.parent)
            # elif TODO history resolve...
            else:
                raise FatalError("None of the expected modes were set")
            # 2. Solve differences
            log_debug("Calculate operations for linking process.")
            dfl = dfs.solve()
            # 3. Eventually manipulate the result
            if self.args.dui:
                log_debug("Reordering operations according to --dui.")
                dfl.run_interpreter(DUIStrategyInterpreter())
            if self.args.skiproot:
                log_debug("Removing operations that require root.")
                dfl.run_interpreter(SkipRootInterpreter())
            # 4. Simmulate a run, print the result or actually resolve the
            # differences
            if self.args.dryrun:
                self.dryrun(dfl)
            elif self.args.plain:
                dfl.run_interpreter(PlainPrintInterpreter())
            elif self.args.print:
                dfl.run_interpreter(PrintInterpreter())
            else:
                self.run(dfl)

    def execute_profiles(self, profiles=None, options=None, directory=None):
        """Imports profiles by name and executes them.

        Args:
            profiles (list): A list of names of profiles that will be executed.
                If this is None, it will be set to what the user set via cli.
            options (dict): A dictionary of default options for root profiles.
                If this is None, it will be set to what the user set via cli.
            directory (str): A default path in which root profiles start.
                If this is None, it will be set to what the user set via cli.
        """
        # Use user arguments as default (can be overwritten for debugging)
        if profiles is None:
            profiles = self.args.profiles
        if options is None:
            options = self.args.opt_dict
        if directory is None:
            directory = self.args.directory

        # Setting arguments for root profiles
        pargs = {}
        pargs["options"] = options
        pargs["directory"] = directory

        # Import and create profiles
        for profilename in profiles:
            self.profiles.append(
                import_profile_class(profilename)(**pargs)
            )
        # And execute them
        for profile in self.profiles:
            profile.generator()

    def print_debuginfo(self):
        """Print out internal values.

        This includes search paths of configs, loaded configs,
        parsed commandline arguments and settings.
        """

        old_section = ""
        for section, name in const.vals():
            if section is None:
                section = "Internal"
            if old_section != section:
                print(const.col_bold + section + ":" + const.col_endc)
                old_section = section
            print(str("   " + name + ": ").ljust(32) + str(const[name]))

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
        print(const.col_bold + profile["name"] + ":" + const.col_endc)
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
        log_debug("Checking operations for errors and conflicts.")
        difflog.run_interpreter(
            CheckProfilesInterpreter(self.installed, const.parent)
        )
        tests = [
            CheckLinksInterpreter(self.installed),
            CheckLinkDirsInterpreter(const.makedirs),
            CheckLinkExistsInterpreter(const.force),
            CheckDynamicFilesInterpreter(False)
        ]
        difflog.run_interpreter(*tests)
        # Gain root if needed
        if not has_root_priveleges():
            log_debug("Checking if root is needed")
            difflog.run_interpreter(GainRootInterpreter())
        else:
            log_debug("uberdot was started with root priveleges")
        # Check blacklist not until now, because the user would need confirm it
        # twice if the programm is restarted with sudo
        difflog.run_interpreter(CheckLinkBlacklistInterpreter(const.superforce))
        # Now the critical part begins, devided into three main tasks:
        # 1. running events before, 2. linking, 3. running events after
        # Each part is surrounded with a try-catch block that wraps every
        # exception which isn't a CustomError into UnkownError and reraises them
        # to handle them in the outer pokemon handler
        old_installed = dict(self.installed)
        # Execute all events before linking and print them
        try:
            if not const.skipevents and not const.skipbefore:
                difflog.run_interpreter(
                    EventExecInterpreter(
                        self.profiles, old_installed, "before"
                    )
                )
                try:
                    # We need to run those tests again because the executed event
                    # might have fucked with some links or dynamic files
                    difflog.run_interpreter(
                        CheckLinkExistsInterpreter(const.force),
                        CheckDynamicFilesInterpreter(False)
                    )
                except CustomError as err:
                    # We add some additional information to the raised errors
                    err._message += "This error occured because at least one of "
                    err._message += "the previously executed events interfered "
                    err._message += "with files that are defined by a profile."
                    raise err
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during before_event execution."
            raise UnkownError(err, msg)
        # Execute operations from difflog
        try:
            # Create Backup in case something wents wrong,
            # so the user can fix the mess we caused
            if os.path.isfile(const.installed_file):
                shutil.copyfile(const.installed_file,
                                const.installed_backup)
            # Execute all operations of the difflog and print them
            difflog.run_interpreter(
                ExecuteInterpreter(self.installed, const.force),
                PrintInterpreter()
            )
            # Remove Backup
            if os.path.isfile(const.installed_backup):
                os.remove(const.installed_backup)
            log_success("Updated links successfully.")
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during linking/unlinking. Some "
            msg += "links or your installed-file may be corrupted! Check the "
            msg += "backup of your installed-file to resolve all possible "
            msg += "issues before you proceed to use this tool!"
            raise UnkownError(err, msg)
        # Execute all events after linking and print them
        try:
            if not const.skipevents and not const.skipafter:
                difflog.run_interpreter(
                    EventExecInterpreter(
                        self.profiles, old_installed, "after"
                    )
                )
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during after_event execution."
            raise UnkownError(err, msg)

    def dryrun(self, difflog):
        """Like `run()` but instead of resolving it it will be just printed out

        Args:
            difflog (DiffLog): The DiffLog that will be checked

        Raises:
            :class:`~errors.CustomError`: Executed interpreters can and will
                raise all kinds of :class:`~errors.CustomError`.
        """
        log_warning("This is just a dry-run! Nothing of the following " +
                    "is actually happening.")
        # Run tests
        log_debug("Checking operations for errors and conflicts.")
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
        log_debug("Checking if root would be needed")
        difflog.run_interpreter(RootNeededInterpreter())
        # Simulate events before
        if not self.args.skipevents and not self.args.skipbefore:
            difflog.run_interpreter(
                EventPrintInterpreter(
                    self.profiles, self.installed, "before"
                )
            )
        # Simulate execution
        difflog.run_interpreter(PrintInterpreter())
        # Simulate events after
        if not self.args.skipevents and not self.args.skipafter:
            difflog.run_interpreter(
                EventPrintInterpreter(
                    self.profiles, self.installed, "after"
                )
            )


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

    def __init__(self, **kwargs):
        if "help" in kwargs:
            # print(kwargs["help"])
            kwargs["description"] = kwargs["help"]
        super().__init__(**kwargs)

    def error(self, message):
        raise UserError(message)


class StdoutFilter(logging.Filter):
    """Custom logging filter that filters all error messages from a stream.
    Used to filter stdout, because otherwise every error would be pushed to
    stdout AND stderr."""

    def filter(self, record):
        """Returns True for all records that have a logging level of
        WARNING or less."""
        return record.levelno <= logging.WARNING


def run_script(name):
    """Act like a script if this was invoked like a script.
    This is needed, because otherwise everything below couldn't
    be traced by coverage."""

    def handle_custom_error(err):
        # An error occured that we (more or less) expected.
        # Print error, a stacktrace and exit
        if isinstance(err, FatalError):
            logger.critical(traceback.format_exc())
            logger.critical(err.message + "\n")
        else:
            log_debug(traceback.format_exc())
            log_error(err.message)
        sys.exit(err.EXITCODE)

    global const
    if name == "__main__":
        const = Const(os.getcwd())
        # Init the logger, further configuration is done when we parse the
        # commandline arguments
        logger = logging.getLogger("root")
        logger.setLevel(logging.INFO)
        ch_out = logging.StreamHandler(stream=sys.stdout)
        ch_out.terminator = ""
        ch_out.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(message)s')
        ch_out.setFormatter(formatter)
        ch_out.addFilter(StdoutFilter())
        # We set up two streamhandlers, so we can log errors automatically
        # to stderr and everything else to stdout
        ch_err = logging.StreamHandler(stream=sys.stderr)
        ch_err.terminator = ""
        ch_err.setLevel(logging.ERROR)
        ch_err.setFormatter(formatter)
        logger.addHandler(ch_out)
        logger.addHandler(ch_err)

        # Create UberDot instance and parse arguments
        uber = UberDot()
        try:
            uber.parse_arguments()
            uber.check_arguments()
        except CustomError as err:
            handle_custom_error(err)
        # Add the users profiles to the python path
        sys.path.append(const.profile_files)
        # Start everything in an exception handler
        try:
            if os.path.isfile(const.installed_backup):
                m = "I found a backup of your installed-file. It's most likely"
                m += " that the last execution of this tool failed. If you "
                m += "are certain that your installed-file is correct you can"
                m += " remove the backup and start this tool again."
                raise PreconditionError(m)
            uber.load_installed()
            uber.execute_arguments()
        except CustomError as err:
            handle_custom_error(err)
        except Exception:
            # This works because all critical parts will catch also all
            # exceptions and convert them into a CustomError
            log_error(traceback.format_exc())
            log_warning("The error above was unexpected. But it's fine," +
                        " I did nothing critical at the time :)")
            sys.exit(100)
        finally:
            # Write installed-file back to json file
            try:
                with open(const.installed_file, "w") as file:
                    file.write(json.dumps(uber.installed, indent=4))
                    file.flush()
                os.chown(const.installed_file, get_uid(), get_gid())
            except Exception as err:
                msg = "An unkown error occured when trying to "
                msg += "write all changes back to the installed-file"
                unkw = UnkownError(err, msg)
                log_error(unkw.message)


run_script(__name__)
