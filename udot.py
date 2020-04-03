#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This is the main module. It implements the UberDot class and a short
startup script.

You can run this directly from the CLI with

.. code:: bash

    python udot.py <arguments>

or you can import UberDot in another script for debugging and testing purposes.
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


import argparse
from distutils.util import strtobool
import csv
import grp
import inspect
import logging
import os
import pwd
import shutil
import sys
import traceback

if os.getenv("COVERAGE_PROCESS_START"):  # pragma: no cover
    import coverage
    coverage.process_startup()

from uberdot.interpreters import *
from uberdot.differencesolver import *
from uberdot.state import get_statefiles
from uberdot.state import get_timestamp_from_path
from uberdot.state import State
from uberdot.utils import *


const = Const()

class UberDot:
    """Bundles all functionality of uberdot.

    This includes things like parsing arguments, loading state files,
    printing information and executing profiles.

    Attributes:
        state (State): The state that is used as a reference
        profiles (list): A list of (generated) profile objects
        args (argparse): The parsed arguments
    """

    def __init__(self):
        """Constructor.

        Initializes attributes and changes the working directory to the
        directory where this module is stored."""
        # Initialise fields
        self.state = None
        self.args = None
        self.profiles = []
        # Change current working directory to the directory of this module
        newdir = os.path.abspath(sys.modules[__name__].__file__)
        newdir = os.path.dirname(newdir)
        os.chdir(newdir)
        # Set environment to var to be used in configs, scripts, profiles, etc
        os.environ["UBERDOT_CWD"] = newdir

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
            dest="mode",
            description="For more help on the modes use 'udot.py <mode> -h'",
        )
        parser_profiles = CustomParser(add_help=False)
        parser_profiles.add_argument(
            "include",
            help="do everything only for this list of profiles",
            nargs="*"
        )

        # Setup top level arguments
        parser.add_argument(
            "-c", "--config",
            help="load an additional config"
        )
        parser.add_argument(
            "-e", "--exclude",
            help="specify a profile that will be ignored in any operations",
            action="append"
        )
        parser.add_argument(
            "--skiproot",
            help="wether all operations that require root permission shall be skiped",
            action=StoreBoolAction
        )
        parser.add_argument(
            "-s", "--summary",
            help="wether just short summaries shall be printed instead of all information",
            action=StoreBoolAction
        )
        group_log_level = parser.add_mutually_exclusive_group()
        group_log_level.add_argument(
            "-v", "--verbose",
            help="print debug messages and tracebacks",
            action="store_const",
            dest="loglevel",
            const="VERBOSE"
        )
        group_log_level.add_argument(
            "--info",
            help="print everything but debug messages (default)",
            action="store_const",
            dest="loglevel",
            const="INFO"
        )
        group_log_level.add_argument(
            "-q", "--quiet",
            help="print nothing but errors",
            action="store_const",
            dest="loglevel",
            const="QUIET"
        )
        group_log_level.add_argument(
            "--silent",
            help="print absolute nothing",
            action="store_const",
            dest="loglevel",
            const="SILENT"
        )
        parser.add_argument(
            "-l", "--log",
            help="specify a file to log to"
        )
        parser.add_argument(
            "--session",
            help="run uberdot in another session",
            default="default"
        )
        parser.add_argument(
            "-d", "--debuginfo",
            help="show loaded settings and internal values",
            action="store_true"
        )
        parser.add_argument(
            "--fix",
            help="specify an action to resolve all fixes with",
            choices=["s", "t", "r", "d", "u"]
        )

        # Setup mode show arguments
        parser_show_selection = CustomParser(add_help=False)
        group_display_selection = parser_show_selection.add_mutually_exclusive_group()
        group_display_selection.add_argument(
            "-u", "--users",
            help="show installed of other users",
            nargs="+"
        )
        group_display_selection.add_argument(
            "-a", "--allusers",
            help="show installed of all users",
            action=StoreBoolAction
        )
        group_display_selection.add_argument(
            "-s", "--state",
            help="select another state file to show (accepts path, number shown in history or timestamp)",
        )
        parser_show_selection.add_argument(
            "-l", "--links",
            help="wether installed links shall be shown",
            action=StoreBoolAction
        )
        parser_show_selection.add_argument(
            "-p", "--profiles",
            help="wether installed profiles shall be shown",
            action=StoreBoolAction
        )
        parser_show_selection.add_argument(
            "-m", "--meta",
            help="wether meta information of profiles and links shall be shown",
            action=StoreBoolAction
        )
        help_text = "display various information about installed profiles"
        parser_show = subparsers.add_parser(
            "show",
            parents=[parser_show_selection, parser_profiles],
            description=help_text,
            help=help_text
        )

        # Setup arguments that are used in both update and remove
        parser_run = CustomParser(add_help=False)
        group_run_mode = parser_run.add_mutually_exclusive_group()
        group_run_mode.add_argument(
            "-d", "--dryrun",
            help="just simulate what would happen",
            action=StoreBoolAction
        )
        group_run_mode.add_argument(
            "-c", "--changes",
            help="print out what changes uberdot will try to perform",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "-m", "--makedirs",
            help="create directories automatically if needed",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "-f", "--force",
            help="overwrite existing files",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "--superforce",
            help="overwrite blacklisted/protected files",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "--skipafter",
            help="wether events after any change shall be skiped",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "--skipbefore",
            help="wether events before any change shall be skiped",
            action=StoreBoolAction
        )
        parser_run.add_argument(
            "--skipevents",
            help="wether all events shall be skiped",
            action=StoreBoolAction
        )
        group_run_mode.add_argument(
            "--debug",
            help=argparse.SUPPRESS,
            action=StoreBoolAction
        )

        # Setup mode update arguments
        help_text="install new or update already installed profiles"
        parser_update = subparsers.add_parser(
            "update",
            parents=[parser_run, parser_profiles],
            description=help_text,
            help=help_text
        )
        parser_update.add_argument(
            "--dui",
            help="use the Delete/Update/Insert strategy for updating links",
            action=StoreBoolAction
        )
        parser_update.add_argument(
            "--directory", help="overwrite the starting directory for profiles"
        )
        parser_update.add_argument(
            "--option",
            help="overwrite default options for profiles",
            dest="opt_dict",
            action=StoreDictKeyPair,
            nargs="+",
            metavar="KEY=VAL"
        )
        parser_update.add_argument(
            "--parent",
            help="overwrite parent profile of profiles"
        )

        # Setup mode remove arguments
        help_text="remove already installed profiles"
        parser_remove = subparsers.add_parser(
            "remove",
            parents=[parser_run, parser_profiles],
            description=help_text,
            help=help_text
        )

        # Setup mode find arguments
        help_text = "helpers to search profiles and dotfiles manually"
        parser_find = subparsers.add_parser(
            "find",
            description=help_text,
            help=help_text
        )
        parser_find.add_argument(
            "-p", "--profiles",
            help="search for profiles",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-d", "--dotfiles",
            help="search for dotfiles",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-t", "--tags",
            help="search for tags",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-c", "--content",
            help="search in file content of profiles/dotfiles",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-n", "--name",
            help="search in the plain names of profiles/dotfiles/tags",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-f", "--filename",
            help="search in filenames of profiles/dotfiles",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-a", "--all",
            help="search everywhere; same as -cnf",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-i", "--ignorecase",
            help="search caseinsensitv (has no effect with -r)",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-r", "--regex",
            help="interprete searchstr as regular expression",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "-l", "--locations",
            help="also show the files where something was found",
            action=StoreBoolAction
        )
        parser_find.add_argument(
            "searchstr",
            help="a string that will be searched for",
            nargs="?"
        )

        # Setup mode timewarp arguments
        help_text = "revert back to a previous state"
        parser_timewarp = subparsers.add_parser(
            "timewarp",
            parents=[parser_run, parser_profiles],
            description=help_text,
            help=help_text
        )
        group_state_selection = parser_timewarp.add_mutually_exclusive_group(required=True)
        # group_state_selection.add_argument(
        #     "--earlier",
        #     help="go back in time for a specific time",
        #     action="store"
        # )
        # group_state_selection.add_argument(
        #     "--later",
        #     help="go forward in time for a specific time",
        #     action="store"
        # )
        group_state_selection.add_argument(
            "--first",
            help="go back to the first recorded state",
            action="store_true"
        )
        group_state_selection.add_argument(
            "--last",
            help="go forward to the last recorded state",
            action="store_true"
        )
        # group_state_selection.add_argument(
        #     "--date",
        #     help="go back (or forward) to this date",
        #     action="store"
        # )
        group_state_selection.add_argument(
            "-s", "--state",
            help="go back to a specific state file (accepts path, number shown in history or timestamp)",
            action="store"
        )

        # Setup mode history arguments
        help_text = "list all previous (or later) states"
        parser_timewarp_list = subparsers.add_parser(
            "history",
            description=help_text,
            help=help_text
        )

        # Setup mode help arguments
        help_text="show man page"
        parser_version = subparsers.add_parser(
            "help",
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
        # TODO add customizable format: logger needs to be initialized properly
        logger.setLevel(const.args.loglevel)
        if const.settings.logfile:
            ch = MaxSizeFileHandler(const.settings.logfile)
            ch.setLevel(logging.DEBUG)
            form = '[%(asctime)s] [%(session)s] [%(levelname)s] - %(message)s'
            formatter = logging.Formatter(form)
            ch.setFormatter(formatter)
            logger.addHandler(ch)

    def check_arguments(self):
        """Checks if parsed arguments/settings are bad or incompatible to
        each other. If not, it raises an UserError."""
        if const.args.mode in ["version", "history", "help"]:
            # If the user just want to get the version number, we should
            # not force him to setup a proper config
            return
        # Check if settings are bad
        if not const.settings.target_files:
            raise UserError("You need to set target_files in your config.")
        if not const.settings.profile_files:
            raise UserError("You need to set profile_files in your config.")
        if const.settings.target_files == const.settings.profile_files:
            msg = "The directories for your profiles and for your dotfiles "
            msg += "are the same."
            raise UserError(msg)
        if not os.path.exists(const.settings.target_files):
            msg = "The directory for your dotfiles '" + const.settings.target_files
            msg += "' does not exist on this system."
            raise UserError(msg)
        if not os.path.exists(const.settings.profile_files):
            msg = "The directory for your profiles '" + const.settings.profile_files
            msg += "' does not exist on this system."
            raise UserError(msg)
        # Check if arguments are bad
        if const.args.mode is None:
            raise UserError("No mode selected.")
        profiles_included = list(set(const.args.include) - set(const.args.exclude))
        if sorted(profiles_included) != sorted(const.args.include):
            msg = "You can not include and exclude a profile at the same time."
            raise UserError(msg)
        if const.args.mode == "find":
            if (not const.find.name and not const.find.filename \
                    and not const.find.content and not const.find.all):
                msg = "You need to set at least one of -n/-f/-c/-a."
                raise UserError(msg)

    def timewarp(self):
        # Get correct state file to warp to
        if const.timewarp.state:
            new_state = State.fromFile(const.timewarp.state)
        # TODO implement
        # elif const.timewarp.date:
        # elif const.timewarp.earlier:
        # elif const.timewarp.later:
        elif const.timewarp.first:
            new_state = State.fromNumber(0)
        elif const.timewarp.last:
            new_state = State.fromNumber(len(get_statefiles())-1)
        if self.state.get_special("snapshot") == new_state.snapshot:
            raise PreconditionError("You are already on this state.")
        log_debug("Calculating operations to perform timewarp.")
        difflog = StateDiffSolver(self.state, new_state).solve()
        # TODO: verify update and install dates a
        # TODO: make events work
        self.run(difflog)
        # Last we update the snapshots
        if const.timewarp.dryrun or const.timewarp.changes or const.timewarp.debug:
            # But skip if run() didn't modify the state file
            return
        if const.args.include or const.args.exclude:
            # State was modified only partly, so this is a completly new snapshot
            self.state.create_snapshot()
        else:
            # State was modified entirely to match new_state, so we
            # update its snapshot reference
            snapshot = get_timestamp_from_path(new_state.own_file)
            self.state.set_special("snapshot", snapshot)

    def execute_arguments(self):
        """Executes whatever was specified via commandline arguments."""
        # Lets do the easy mode first
        if const.args.mode == "find":
            self.search()
            return
        if const.args.mode == "version":
            log(const.settings.col_emph + "Version: " + const.col_endc + const.VERSION)
            return
        if const.args.mode == "help":
            os.execvp("man", ["-l", normpath("docs/sphinx/build/man/uberdot.1")])
        # For the next mode we need a loaded state
        self.state = State.current()
        self.fix()
        if const.args.mode == "show":
            self.show()
        elif const.args.mode == "history":
            self.list_states()
        elif const.args.mode == "timewarp":
            self.timewarp()
        else:
            # The previous mode just printed stuff, but here we
            # have to actually do something:
            # 0. Figure out which profiles we are talking about
            # TODO profilenames could be used at other places as well
            profilenames = const.args.include
            if not profilenames:
                profilenames = self.state.keys()
            if not profilenames:
                msg = "There are no profiles installed and no profiles "
                msg += "explicitly specified to be included."
                raise UserError(msg)
            # 1. Decide how to solve the differences and setup DiffSolvers
            if const.args.mode == "remove":
                log_debug("Calculating operations to remove profiles.")
                dfs = UninstallDiffSolver(self.state, profilenames)
            elif const.args.mode == "update":
                log_debug("Calculating operations to update profiles.")
                self.execute_profiles(profilenames)
                profile_results = [p.result for p in self.profiles]
                dfs = UpdateDiffSolver(self.state,
                                       profile_results,
                                       const.update.parent)
            else:
                raise FatalError("None of the expected modes were set.")
            # 2. Solve differences
            dfl = dfs.solve()
            # 3. Eventually manipulate the result
            if const.args.mode == "update":
                if const.update.dui:
                    log_debug("Reordered operations to use DUI-strategy.")
                    dfl.run_interpreter(DUIStrategyInterpreter())
            if const.args.skiproot:
                log_debug("Removing operations that require root.")
                dfl.run_interpreter(SkipRootInterpreter())
            # 4. Simmulate a run, print the result or actually resolve the
            # differences
            self.run(dfl)

    def list_states(self):
        statefiles = get_statefiles()
        current = statefiles.pop(0)
        snapshot = self.state.get_special("snapshot") if "snapshot" in self.state.get_specials() else None
        for nr, file in enumerate(statefiles):
            timestamp = get_timestamp_from_path(file)
            msg = "[" + str(nr+1) + "] "
            if snapshot==timestamp:
                msg += const.settings.col_emph + "(current) " + const.col_endc
            temp_state =  State.fromTimestamp(timestamp)
            msg += "ID: " + timestamp
            msg += "  Date: " + timestamp_to_string(timestamp)
            msg += "  Version: " + temp_state.get_special("version")
            root_profiles = filter(lambda x: "parent" not in temp_state[x], temp_state.keys())
            msg += "  Root profiles: " + " ".join(root_profiles)
            print(msg)


    def fix(self):
        log_debug("Checking state file consistency.")
        # Calc difflog between state and filesystem to figure out
        # if there are inconsistencies
        difflog = StateFilesystemDiffFinder(self.state).solve()
        if difflog:
            log_warning("Some tracked links were manually changed.")
            # Print summary to give user an idea of what have changed
            difflog.run_interpreter(PrintInterpreter())
            # Get selection from user
            selection = const.args.fix
            if not selection:
                log("How would you like to fix those changes?")
                selection = user_choice(
                    ("S", "Skip fixing"), ("T", "Take over all changes"),
                    ("R", "Restore all links"), ("U", "Untrack all changes"),
                    ("D", "Decide for each link")
                )
            else:
                log("Autofixing using mode " + const.args.fix + ".")
            # Calculate difflog again depending on selection.
            if selection == "s":
                return
            diffsolver = StateFilesystemDiffSolver(self.state, action=selection)
            difflog = diffsolver.solve()
            # Execute difflog. First some obligatory checks
            log_debug("Checking operations for errors and conflicts.")
            difflog.run_interpreter(
                CheckFileOverwriteInterpreter(),
                CheckDiffsolverResultInterpreter(self.state)
            )
            # Also allow to skip root here
            if const.args.skiproot:
                difflog.run_interpreter(SkipRootInterpreter())
            # Gain root if needed
            if not has_root_priveleges():
                log_debug("Checking if root is required for fixing.")
                difflog.run_interpreter(
                    GainRootInterpreter()
                )
            # Finally execute
            try:
                interpreters = [ExecuteInterpreter(self.state)]
                if const.args.summary:
                    interpreters.append(PrintSummaryInterpreter())
                else:
                    interpreters.append(PrintInterpreter())
                difflog.run_interpreter(*interpreters)
            except CustomError:
                raise
            except Exception as err:
                msg = "An unkown error occured when trying to fix the state "
                msg += "file. Your state file is probably still corrupted. "
                msg += "Uberdot will again try to fix the corruptions the next"
                msg += " time you use it. Please just make sure to to resolve "
                msg += "the unkown error before you proceed to use this tool."
                raise UnkownError(err, msg)


    def execute_profiles(self, profilenames):
        """Imports profiles by name and executes them. """
        # Import and create profiles
        for profilename in profilenames:
            if profilename in const.args.exclude:
                log_debug("'" + profilename + "' is in exclude list." +
                          " Skipping generation of profile...")
            else:
                self.profiles.append(
                    import_profile(profilename)()
                )
        # And execute/generate them
        for profile in self.profiles:
            profile.generator()

    def print_debuginfo(self):
        """Print out internal values.

        This includes search paths of configs, loaded configs,
        parsed commandline arguments and settings.
        """
        old_section = ""
        for name, props in const.get_constants(mutable=0):
            section = props.section
            if props.section is None:
                section = "Internal"
            if old_section != section:
                print(const.settings.col_emph + section + ":" + const.col_endc)
                old_section = section
            if name in ["col_endc", "col_noemph"]:
                continue
            value = props.value
            if name.startswith("col_"):
                value = value + value.encode("unicode_escape").decode("utf-8")
                value += const.col_endc
            if (name == "cfg_files" or name == "cfg_search_paths") and value:
                print(str("   " + name + ": ").ljust(32) + str(value[0]))
                for item in value[1:]:
                    print(" " * 32 + str(item))
            else:
                print(str("   " + name + ": ").ljust(32) + str(value))

    def show(self):
        """Print out the state file in a readable format.

        Prints only the profiles specified in the commandline arguments. If
        none are specified it prints all profiles of the state file."""
        if const.show.state is not None:
            temp_state = State(const.show.state)
            for profile in temp_state.values():
                if not const.args.include or profile["name"] in const.args.include:
                    self.print_profile(profile)
        else:
            last_user = ""
            for user, profile in self.state.get_profiles():
                # Skip users that shall not be printed
                if not const.show.allusers:
                    if const.show.users:
                        if user not in const.show.users:
                            continue
                    elif const.user != user:
                        continue
                # Print the next user
                if user != last_user:
                    # But only if other users shall be shown
                    if const.show.allusers or const.show.users:
                        print(const.settings.col_emph + "User: " + const.col_endc + user)
                    last_user = user
                # Show all profiles that are specified or all if none was specified
                if not const.args.include or profile["name"] in const.args.include:
                    self.print_profile(profile)

    def print_profile(self, profile):
        """Prints a single installed profile.

        Args:
            profile (dict): The profile that will be printed
        """
        if profile["name"] in const.args.exclude:
            log_debug("'" + profile["name"] + "' is in exclude list. Skipping...")
            return
        tab = "  " if const.show.users or const.show.allusers else ""
        if const.show.profiles or (not const.show.links and not const.show.meta):
            col = const.settings.col_emph if const.show.links or const.show.meta or not const.show.profiles else ""
            profile_header = tab + col + profile["name"] + const.col_endc
            if const.show.links or const.show.meta:
                profile_header += ":"
            print(profile_header)
            tab += "  "
            if const.show.meta:
                print(tab + "Installed: " + profile["installed"])
                print(tab + "Updated: " + profile["updated"])
                if "parent" in profile:
                    print(tab + "Subprofile of: " + profile["parent"])
                if "profiles" in profile:
                    print(tab + "Has Subprofiles: " + ", ".join(
                        [s["name"] for s in profile["profiles"]]
                    ))
        if const.show.links or (not const.show.profiles and not const.show.meta):
            for symlink in profile["links"]:
                print(tab + symlink["from"] + "  →  " + symlink["to"])
                if const.show.meta:
                    print(
                        tab + "    Owner: " + symlink["owner"] +
                        "   Permission: " + str(symlink["permission"]) +
                        "   Secure: " + "yes" if symlink["secure"] else "no" +
                        "   Updated: " + symlink["date"]
                    )

    def search(self):
        def hlsearch(text, pattern):
            all_results = []
            # Search in each line of text independently and collect all results
            # Returns always the full line where something was found, but
            # colors the found substring red
            for line in text.split("\n"):
                if const.find.regex:
                    # Searching with regex
                    match = re.search(pattern, line)
                    if match:
                        # Colorize match in line and add to results
                        result = line[:match.start()] + const.settings.col_fail
                        result += line[match.start():match.end()]
                        result += const.col_endc + line[match.end():]
                        all_results.append(result)
                else:
                    # Plain search
                    # Lowers text and pattern if ignorecase was set
                    try:
                        if const.find.ignorecase:
                            idx = line.lower().index(pattern.lower())
                        else:
                            idx = line.index(pattern)
                    except ValueError:
                        # Nothing was found in this line
                        continue
                    # Colorize match in line and add to results
                    result = line[:idx] + const.settings.col_fail
                    result += line[idx:idx+len(pattern)]
                    result += const.col_endc + line[idx+len(pattern):]
                    all_results.append(result)
            return all_results

        result = []
        nothing_selected = (not const.find.profiles and not const.find.dotfiles
                            and not const.find.tags)
        # Search for profiles
        if const.find.profiles or nothing_selected:
            # Search in filename (full paths of files in the profile directory)
            if const.find.filename or const.find.all:
                for file in walk_profiles():
                    highlighted = hlsearch(file, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
            for file, pname in get_available_profiles():
                if pname in const.args.exclude:
                    log_debug("'" + pname + "' is in exclude list. Skipping...")
                    continue
                # Search in names (class names of all available profiles)
                if const.find.name or const.find.all:
                    highlighted = hlsearch(pname, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
                # Search in content (source code of each available profile)
                if const.find.content or const.find.all:
                    source = "".join(get_profile_source(pname, file))
                    highlighted = hlsearch(source, const.find.searchstr)
                    result += [(file, item) for item in highlighted]

        # Search for dotfiles
        if const.find.dotfiles or nothing_selected:
            for root, name in walk_dotfiles():
                file = os.path.join(root, name)
                # Search in names (only file basenames, without tag)
                if const.find.name or const.find.all:
                    searchtext = name
                    if const.settings.tag_separator in searchtext:
                        idx = searchtext.index(const.settings.tag_separator)
                        searchtext = searchtext[idx+1:]
                    highlighted = hlsearch(searchtext, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
                # Search in filename (full paths of dotfiles)
                if const.find.filename or const.find.all:
                    highlighted = hlsearch(file, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
                # Search in content (full content of each dotfile)
                if const.find.content or const.find.all:
                    try:
                        searchtext = open(file).read()
                        highlighted = hlsearch(searchtext, const.find.searchstr)
                        result += [(file, item) for item in highlighted]
                    except UnicodeDecodeError:
                        # This is not a text file (maybe an image or encrypted)
                        pass
        # Search for tags (this only collects the tags from filenames because
        # it doesn't make sense to search in the content of files or whatever)
        if const.find.tags:
            tags = []
            sep = const.settings.tag_separator
            # Collect tags first
            for root, name in walk_dotfiles():
                file = os.path.join(root, name)
                if sep in name:
                    tag = name[:name.index(sep)+len(sep)-1]
                    if const.find.locations:
                        highlighted = hlsearch(tag, const.find.searchstr)
                        result += [(file, item) for item in highlighted]
                    elif tag not in tags:
                        tags.append(tag)
            for tag in tags:
                highlighted = hlsearch(tag, const.find.searchstr)
                result += [(file, item) for item in highlighted]

        # Print all the results
        if const.find.locations:
            # Either with file paths (in the order that we found them)
            for i, item in enumerate(result):
                if item in result[i+1:]:
                    result.pop(i)
            for file, entry in result:
                print(file + ": " + entry)
        else:
            # or just what was found (in alphabetical order)
            for entry in sorted(list(set([item[1] for item in result]))):
                print(entry)

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
        if const.subcommand.debug:
            difflog.run_interpreter(PrintPlainInterpreter())
            return
        elif const.subcommand.changes:
            difflog.run_interpreter(PrintInterpreter())
            return
        elif const.subcommand.dryrun:
            log_warning("This is just a dry-run! Nothing of the following " +
                        "is actually happening.")
        # Run integration tests on difflog
        log_debug("Checking operations for errors and conflicts.")
        # These tests should be run before the other tests, because they
        # would fail anyway if these tests don't pass
        difflog.run_interpreter(
            CheckDiffsolverResultInterpreter(self.state),
            CheckProfilesInterpreter(self.state)
        )
        # Run the rest of the tests
        tests = [
            CheckLinksInterpreter(self.state),
            CheckLinkDirsInterpreter(),
            CheckFileOverwriteInterpreter(),
            CheckDynamicFilesInterpreter()
        ]
        difflog.run_interpreter(*tests)
        # Gain root if needed
        if not has_root_priveleges():
            log_debug("Checking if root is required.")
            if const.subcommand.dryrun:
                difflog.run_interpreter(RootNeededInterpreter())
            else:
                difflog.run_interpreter(GainRootInterpreter())
        else:
            log_debug("uberdot was started with root priveleges.")
        # Check blacklist not until now, because the user would need confirm it
        # twice if the programm is restarted with sudo
        difflog.run_interpreter(CheckLinkBlacklistInterpreter())
        # Now the critical part begins, devided into three main tasks:
        # 1. running events before, 2. linking, 3. running events after
        # Each part is surrounded with a try-catch block that wraps every
        # exception which isn't a CustomError into UnkownError and reraises them
        # to handle them in the outer pokemon handler

        # The events need to use the original state file to access to
        # correct uninstall events
        old_state = self.state.copy()
        # Execute all events before linking and print them
        try:
            if not const.subcommand.skipevents and not const.subcommand.skipbefore:
                inter = EventPrintInterpreter if const.subcommand.dryrun else EventExecInterpreter
                difflog.run_interpreter(
                    inter(old_state, "before")
                )
                try:
                    # We need to run this test again because the executed event
                    # might have fucked with some links
                    difflog.run_interpreter(
                        CheckDiffsolverResultInterpreter(
                            self.state, error_type=PreconditionError
                        ),
                        CheckFileOverwriteInterpreter()
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
            # Execute all operations of the difflog and print them
            interpreters = []
            if not const.subcommand.dryrun:
                interpreters.append(ExecuteInterpreter(self.state))
            if const.args.summary:
                interpreters.append(PrintSummaryInterpreter())
            else:
                interpreters.append(PrintInterpreter())
            difflog.run_interpreter(*interpreters)
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during linking/unlinking. Some "
            msg += "links or your state file may be corrupted. In most "
            msg += "cases uberdot will fix all corruptions by itself the next "
            msg += "time you use it. Please just make sure to to resolve the "
            msg += "unkown error before you proceed to use this tool."
            raise UnkownError(err, msg)
        # Execute all events after linking and print them
        try:
            if not const.subcommand.skipevents and not const.subcommand.skipafter:
                interpreter = EventPrintInterpreter if const.subcommand.dryrun else EventExecInterpreter
                difflog.run_interpreter(
                    interpreter(old_state, "after")
                )
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during after_event execution."
            raise UnkownError(err, msg)


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


class StoreBoolAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        for option in option_strings:
            if option.startswith("--"):
                option_strings.append("--no-" + option[2:])
                break
        kwargs["nargs"] = 0
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string.startswith("--no-"):
            setattr(namespace, self.dest, False)
        else:
            setattr(namespace, self.dest, True)


class CustomParser(argparse.ArgumentParser):
    """Custom argument parser that raises an UserError instead of writing
    the error to stderr and exiting by itself."""

    def __init__(self, **kwargs):
        if "help" in kwargs:
            kwargs["description"] = kwargs["help"]
        super().__init__(**kwargs)

    def error(self, message):
        raise UserError(message)

    def parse_args(self, args=None, namespace=None):
        # Prepare function arguments
        if args is None:
            args = sys.argv[1:]
        if namespace is None:
            namespace = argparse.Namespace()
        # Parse commandline like usually just to make sure the user entered
        # a valid combition of arguments and subcommands
        super().parse_args(args, namespace)
        # Then we prepare argv for the actual parsing. Therefore we will
        # devide it by subcommands and parse them individual.
        # First initialize some stuff that we will need for this
        subparsers = self._subparsers._actions[1].choices
        def max_count(nargs):
            # Returns the maximal number of arguments for a nargs value
            # Returns -1 if infinite arguments are allowed
            if isinstance(nargs, int):
                return nargs
            if nargs == "?" or nargs is None:
                return 1
            return -1
        split_argv = [[]]  # This is where we store the prepared argv
        max_arg_count = 0
        subp = self
        # Store for each positional of the current subparser how many
        # arguments are allowed at max
        positional_arg_counts = [
            max_count(action.nargs) for action in subp._actions
            if not action.option_strings
        ]
        # Stores wether a positional was read at last
        reading_positional = False
        for c in sys.argv[1:]:
            # is optional
            if c.startswith("-"):
                # stop counting arguments of previous option
                max_arg_count = 0
                # add argument to last subparsers arguments
                split_argv[-1].append(c)
                # if we read a positional previously, we can stop now
                if reading_positional:
                    positional_arg_counts.pop(0)
                reading_positional = False
                if c != "--":
                    # This is not only the end of some option, but a new option
                    com = c
                    if c[1] != "-":  # short option
                        # get the last short option incase options are chained together
                        com = "-" + c[-1]
                    # determine the new maximal count of arguments for this optional
                    nargs = subp._optionals._option_string_actions[com].nargs
                    max_arg_count = max_count(nargs)
            # is postional
            else:
                if max_arg_count != 0:
                    # this belongs to a previous optional
                    split_argv[-1].append(c)
                    max_arg_count -= 1
                elif c in subparsers:
                    # this is a new subcommand
                    split_argv.append([c])
                    # reset the current subparser, argument_count and positionals
                    subp = subparsers[c]
                    max_arg_count = 0
                    reading_positional = False
                    positional_arg_counts = [
                        max_count(action.nargs) for action in subp._actions
                        if not action.option_strings
                    ]
                else:
                    if positional_arg_counts and positional_arg_counts[0] != 0:
                        # this belongs to a postional
                        split_argv[-1].append(c)
                        positional_arg_counts[0] -= 1
                        reading_positional = True
                    else:
                        # TODO does this ever trigger?
                        raise UserError("No such mode: " + c)
        # Initialize namespace and parse until first subcommand
        result = self.parse_command(split_argv[0], subparsers.keys())
        # Parse each subcommand
        ns = result
        for argv in split_argv[1:]:
            ns = subparsers[argv[0]].parse_command(argv, subparsers.keys(), result=ns)
        return result

    def parse_command(self, argv, modes, result=None):
        n = argparse.Namespace()
        if result is not None:
            setattr(result, argv[0], n)
        if argv and argv[0] in modes:
            setattr(result, "mode", argv[0])
            argv = argv[1:]
        super().parse_args(argv, namespace=n)
        return n


class StdoutFilter(logging.Filter):
    """Custom logging filter that filters all error messages from a stream.
    Used to filter stdout, because otherwise every error would be pushed to
    stdout AND stderr."""

    def filter(self, record):
        """Returns True for all records that have a logging level of
        WARNING or less."""
        return record.levelno <= logging.WARNING


class MaxSizeFileHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def emit(self, record):
        print(record.__dict__)
        msg = self.format(record)
        # Remove all color codes
        msg = msg.replace(const.col_endc, "")
        msg = msg.replace(const.col_noemph, "")
        for name, attr in const.settings.get_constants():
            if name.startswith("col_"):
                msg = msg.replace(attr.value, "")
        # Write into file, but make sure not to exceed logfilesize
        msg = msg.splitlines(True)
        content = []
        if os.path.exists(self.filename):
            with open(self.filename, "r") as fin:
                content = fin.read().splitlines(True)
        content = content + msg
        content = content[-const.settings.logfilesize:]
        with open(self.filename, "w") as fout:
            fout.writelines(content)


class CustomRecordLogger(logging.Logger):
    def makeRecord(self, *args, **kwargs):
        if "extra" not in kwargs or kwargs["extra"] is None:
            kwargs["extra"] = {}
        kwargs["extra"]["session"] = const.args.session
        super().makeRecord(*args, **kwargs)


def run_script(name):
    """Act like a script if this was invoked like a script.
    This is needed, because otherwise everything below couldn't
    be traced by coverage."""

    if name == "__main__":
        # Init the logger, further configuration is done when we parse the
        # commandline arguments
        logging.setLoggerClass(CustomRecordLogger)
        logger = logging.getLogger("root")
        print(type(logger))
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

        # Start everything in a try block with pokemon handler
        try:
            # Create UberDot instance and parse arguments
            udot = UberDot()
            udot.parse_arguments()
            udot.check_arguments()
            # Add the users profiles to the python path
            sys.path.append(const.settings.profile_files)
            # Go
            udot.execute_arguments()
        except CustomError as err:
            # An error occured that we (more or less) expected.
            # Print error, a stacktrace and exit
            if isinstance(err, FatalError):
                logger.critical(traceback.format_exc())
                logger.critical(err.message + "\n")
            else:
                log_debug(traceback.format_exc())
                log_error(err.message)
            sys.exit(err.EXITCODE)
        except Exception:
            # This works because all critical parts will catch also all
            # exceptions and convert them into a CustomError
            log_error(traceback.format_exc())
            log_warning("The error above was unexpected. But it's fine," +
                        " I did nothing critical at the time :)")
            sys.exit(100)


run_script(__name__)
