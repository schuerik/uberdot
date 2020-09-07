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
import pickle
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
from uberdot.state import State
from uberdot.state import GlobalState
from uberdot.utils import *
from uberdot.profile import ProfileLoader


const = Const()
globalstate = GlobalState()
logger = None


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
        # TODO: does this even work with packaging later?
        newdir = os.path.abspath(sys.modules[__name__].__file__)
        newdir = os.path.dirname(newdir)
        os.chdir(newdir)
        # Set environment var to be used in configs, scripts, profiles, etc
        os.environ["UBERDOT_CWD"] = newdir

    @staticmethod
    def __init_logger():
        global logger
        # Init the logger, further configuration is done when we parse the
        # commandline arguments
        logging.setLoggerClass(CustomRecordLogger)
        logger = logging.getLogger("root")
        logger.setLevel(logging.DEBUG)
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
            help="log everything also into logfile",
            action=StoreBoolAction
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
            action=StoreDictKeyPairAction,
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
        group_state_selection.add_argument(
            "--earlier",
            help="go back in time for a specific time",
            action="store"
        )
        group_state_selection.add_argument(
            "--later",
            help="go forward in time for a specific time",
            action="store"
        )
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
        group_state_selection.add_argument(
            "--date",
            help="go back (or forward) to this date",
            action="store"
        )
        group_state_selection.add_argument(
            "-s", "--state",
            help="go back to a specific state file (accepts path, number shown in history or timestamp)",
            action="store"
        )

        # TODO new mode to sync files back to target_dir
        # Setup mode sync arguments
        help_text = "Synchronise changes made to dotfiles back to the dotfile directory"
        parser_sync = subparsers.add_parser(
            "sync",
            description=help_text,
            help=help_text
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
        parser_man = subparsers.add_parser(
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

        # Setup mode resume arguments (this mode is hidden, so it has no help text)
        parser_resume = subparsers.add_parser("resume")

        # Read arguments
        try:
            args = parser.parse_args(arguments)
        except argparse.ArgumentError as err:
            raise UserError(err.message)

        # Load args and configs into const
        const.load(args)

        if args.debuginfo:
            # At this point everything is loaded, so we print debuginfo
            # immediatly so no exception that might occur later on
            # won't "shadow" this output
            self.print_debuginfo()
            sys.exit(0)

        # Configure logger
        logger.setLevel(const.args.loglevel)
        if const.args.log:
            ch = NoColorFileHandler(const.settings.logfile)
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter(const.settings.logfileformat)
            ch.setFormatter(formatter)
            logger.addHandler(ch)

    def check_arguments(self):
        """Checks if parsed arguments/settings are bad or incompatible to
        each other. If not, it raises an UserError."""
        # TODO check that root is not used except when in resume mode or explictly allowed
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
        # profiles_included = list(set(const.args.include) - set(const.args.exclude))
        # if sorted(profiles_included) != sorted(const.args.include):
        #     msg = "You can not include and exclude a profile at the same time."
        #     raise UserError(msg)
        if const.args.mode == "find":
            if (not const.find.name and not const.find.filename \
                    and not const.find.content and not const.find.all):
                msg = "You need to set at least one of -n/-f/-c/-a."
                raise UserError(msg)

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

    def fix(self):
        log_debug("Checking state file consistency.")
        # Calc difflog between state and filesystem to figure out
        # if there are inconsistencies
        difflog = StateFilesystemDiffFinder().solve()
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
            diffsolver = StateFilesystemDiffSolver(action=selection)
            difflog = diffsolver.solve()
            # Execute difflog. First some obligatory checks
            log_debug("Checking operations for errors and conflicts.")
            difflog.run_interpreter(
                CheckFileOverwriteInterpreter(),
                CheckDiffsolverResultInterpreter()
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
                interpreters = [ExecuteInterpreter()]
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

    def generate_profiles(self):
        """Imports profiles by name and executes them. """
        profiles = []
        # Import and create profiles
        for profilename in self.get_profilenames():
            if profilename in const.args.exclude:
                log_debug("'" + profilename + "' is in exclude list." +
                          " Skipping generation of profile...")
            else:
                profiles.append(ProfileLoader().new_object(profilename))
        # And execute/generate them
        for profile in profiles:
            profile.start_generation()
        return [p.result for p in profiles]

    def execute_arguments(self):
        """Executes whatever was specified via commandline arguments."""
        # Lets do the easy mode first
        if const.args.mode == "find":
            self._exec_find()
            return
        if const.args.mode == "version":
            self._exec_version()
            return
        if const.args.mode == "help":
            # Replaces the current process, so no return needed here
            self._exec_help()
        # For the remaining modes we need a loaded state
        globalstate.load()
        self.state = globalstate.current
        # Try to fix it, to make sure it matches the actual state of the filesystem
        self.fix()
        if const.args.mode == "show":
            self._exec_show()
        elif const.args.mode == "history":
            self._exec_history()
        elif const.args.mode == "timewarp":
            self._exec_timewarp()
        elif const.args.mode == "remove":
            self._exec_remove()
        elif const.args.mode == "update":
            self._exec_update()
        elif const.args.mode == "resume":
            self._exec_resume()
        else:
            raise FatalError("None of the expected modes were set.")

    def get_profilenames(self):
        # profilenames is equal to included profiles if provided
        profilenames = const.mode_args.include
        # Otherwise it is equal to the list of already installed root profiles
        if not profilenames:
            profilenames = self.state.keys()
            if not profilenames:
                msg = "There are no profiles installed and no profiles "
                msg += "explicitly specified to be included."
                raise UserError(msg)
        # Also all explictly excluded profiles will be removed from profilenames
        for i, profilename in enumerate(profilenames[:]):
            if profilename in const.args.exclude:
                del profilenames[i]
        return profilenames

    @staticmethod
    def _hlsearch(text, pattern):
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

    def find_dotfile(self, searchstr):
        result = []
        for file in walk_dotfiles():
            # Search in names (only file basenames, without tag)
            if const.find.name or const.find.all:
                searchtext = os.path.basename(file)
                if const.settings.tag_separator in searchtext:
                    idx = searchtext.index(const.settings.tag_separator)
                    searchtext = searchtext[idx+1:]
                highlighted = _hlsearch(searchtext, const.find.searchstr)
                result += [(file, item) for item in highlighted]
            # Search in filename (full paths of dotfiles)
            if const.find.filename or const.find.all:
                highlighted = _hlsearch(file, const.find.searchstr)
                result += [(file, item) for item in highlighted]
            # Search in content (full content of each dotfile)
            if const.find.content or const.find.all:
                try:
                    searchtext = open(file).read()
                    highlighted = _hlsearch(searchtext, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
                except UnicodeDecodeError:
                    # This is not a text file (maybe an image or encrypted)
                    pass
        return result

    def find_profiles(self, searchstr):
        result = []
        # Search in filename (full paths of files in the profile directory)
        if const.find.filename or const.find.all:
            for file in walk_profiles():
                highlighted = _hlsearch(file, const.find.searchstr)
                result += [(file, item) for item in highlighted]
        for file, pname in get_available_profiles():
            if pname in const.args.exclude:
                log_debug("'" + pname + "' is in exclude list. Skipping...")
                continue
            # Search in names (class names of all available profiles)
            if const.find.name or const.find.all:
                highlighted = _hlsearch(pname, const.find.searchstr)
                result += [(file, item) for item in highlighted]
            # Search in content (source code of each available profile)
            if const.find.content or const.find.all:
                source = "".join(get_profile_source(pname, file))
                highlighted = _hlsearch(source, const.find.searchstr)
                result += [(file, item) for item in highlighted]
        return result

    def find_tags(self, searchstr):
        result = []
        tags = []
        sep = const.settings.tag_separator
        # Collect tags first
        for file in walk_dotfiles():
            name = os.path.basename(file)
            if sep in name:
                tag = name[:name.index(sep)+len(sep)-1]
                if const.find.locations:
                    highlighted = _hlsearch(tag, const.find.searchstr)
                    result += [(file, item) for item in highlighted]
                elif tag not in tags:
                    tags.append(tag)
        for tag in tags:
            highlighted = _hlsearch(tag, const.find.searchstr)
            result += [(file, item) for item in highlighted]
        return result

    def _exec_find(self):
        result = []
        nothing_selected = (not const.find.profiles and not const.find.dotfiles
                            and not const.find.tags)
        # Search for profiles
        if const.find.profiles or nothing_selected:
            result = self.find_profiles(const.find.searchstr)

        # Search for dotfiles
        if const.find.dotfiles or nothing_selected:
            result = self.find_dotfile(const.find.searchstr)
        # Search for tags (this only collects the tags from filenames because
        # it doesn't make sense to search in the content of files or whatever)
        if const.find.tags:
            result = self.find_tags(const.find.searchstr)

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

    def _exec_help(self):
        log_debug("Starting man with local docs.")
        os.execvp("man", ["-l", abspath("docs/sphinx/build/man/uberdot.1")])

    def _exec_history(self):
        snapshot = self.state.get_special("snapshot") if "snapshot" in self.state.get_specials() else None
        for nr, file in enumerate(self.state.get_snapshots()):
            timestamp = get_timestamp_from_path(file)
            msg = "[" + str(int(nr)+1) + "] "
            if snapshot == timestamp:
                msg += const.settings.col_emph + "(current) " + const.col_endc
            temp_state = State.fromTimestamp(timestamp)
            msg += "ID: " + timestamp
            msg += "  Date: " + timestamp_to_string(timestamp)
            msg += "  Version: " + temp_state.get_special("version")
            root_profiles = filter(lambda x: "parent" not in temp_state[x], temp_state.keys())
            msg += "  Root profiles: " + " ".join(root_profiles)
            print(msg)

    def _exec_remove(self):
        log_debug("Calculating operations to remove profiles.")
        dfs = UninstallDiffSolver(self.get_profilenames())
        dfl = dfs.solve()
        if const.args.skiproot:
            dfl.run_interpreter(SkipRootInterpreter())
        self.resolve_difflog(dfl)

    # TODO this needs testing for sure
    def _exec_resume(self):
        log_debug("Loading pickle of previous uberdot process.")
        pickle_path = abspath("uberdot.pickle", origin=const.internal.owd)
        const_obj, dfl = pickle.load(sys.stdin)
        Const.__load_object(const_obj)
        log_debug("Resuming previous process.")
        self.resolve_difflog(dfl)
        log_debug("Removing pickle.")
        os.remove("uberdot.pickle")

    def _exec_show(self):
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
            for user, profile in globalstate.get_profiles():
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

    def _exec_timewarp(self):
        cst = const.timewarp
        # Get correct state file to warp to
        if cst.state:
            new_state = State.fromFile(cst.state)
        elif cst.date:
            new_state = State.fromTimestampBefore(cst.date)
        elif cst.earlier or cst.later:
            delta = cst.earlier if cst.earlier else -cst.later
            if "snapshot" in self.state.get_specials():
                time = int(self.state.get_special("snapshot")) - delta
            else:
                time = int(get_timestamp_now()) - delta
            new_state = State.fromTimestampBefore(time)
        elif cst.first:
            new_state = State.fromIndex(0)
        elif cst.last:
            new_state = State.fromIndex(-1)
        if self.state.get_special("snapshot") == new_state.get_special("snapshot"):
            raise PreconditionError("You are already on this state.")
        log_debug("Calculating operations to perform timewarp.")
        difflog = StateDiffSolver(self.state, new_state).solve()
        self.resolve_difflog(difflog)
        # Last we update the snapshots
        if cst.dryrun or cst.changes or cst.debug:
            # But skip if resolve_difflog() didn't modify the state file
            return
        # TODO what about --skiproot?
        # TODO the following is still critical but doesnt handle unexpected errors
        if const.args.include or const.args.exclude:
            # State was modified only partly, so this is a completly new snapshot
            self.state.create_snapshot()
        else:
            # State was modified entirely to match new_state, so we
            # update its snapshot reference
            snapshot = get_timestamp_from_path(new_state.file)
            self.state.set_special("snapshot", snapshot)

    def _exec_update(self):
        profile_results = self.generate_profiles()
        dfs = UpdateDiffSolver(profile_results, const.mode_args.parent)
        dfl = dfs.solve()
        if const.update.dui:
            dfl.run_interpreter(DUIStrategyInterpreter())
        if const.args.skiproot:
            dfl.run_interpreter(SkipRootInterpreter())
        self.resolve_difflog(dfl)

    def _exec_version(self):
        log(const.settings.col_emph + "Version: " + const.col_endc + const.VERSION)

    def _create_resume_pickle(self, difflog):
        return pickle.dumps([const, difflog])

    def resolve_difflog(self, difflog):
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
        if const.mode_args.debug:
            difflog.run_interpreter(PrintPlainInterpreter())
            return
        elif const.mode_args.changes:
            difflog.run_interpreter(PrintInterpreter())
            return
        elif const.mode_args.dryrun:
            log_warning("This is just a dry-run! Nothing of the following " +
                        "is actually happening.")
        # Run integration tests on difflog
        log_debug("Checking operations for errors and conflicts.")
        # These tests should be run before the other tests, because they
        # would fail anyway if these tests don't pass
        difflog.run_interpreter(
            CheckDiffsolverResultInterpreter(),
            CheckProfilesInterpreter()
        )
        # Run the rest of the tests
        tests = [
            CheckLinksInterpreter(),
            CheckLinkDirsInterpreter(),
            CheckFileOverwriteInterpreter(),
            CheckDynamicFilesInterpreter()
        ]
        difflog.run_interpreter(*tests)
        # Gain root if needed
        if not has_root_priveleges():
            log_debug("Checking if root is required.")
            root_interpreter = RootNeededInterpreter()
            difflog.run_interpreter(root_interpreter)
            if not const.mode_args.dryrun and root_interpreter.logged:
                process = Popen([sys.executable, "resume"], stdin=PIPE)
                process.communicate(self._create_resume_pickle(difflog))
                process.wait()
                return
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
            if not const.mode_args.skipevents and not const.mode_args.skipbefore:
                inter = EventPrintInterpreter if const.mode_args.dryrun else EventExecInterpreter
                difflog.run_interpreter(
                    inter(old_state, "before")
                )
                try:
                    # We need to run this test again because the executed event
                    # might have fucked with some links
                    difflog.run_interpreter(
                        CheckDiffsolverResultInterpreter(
                            error_type=PreconditionError
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
            if not const.mode_args.dryrun:
                interpreters.append(ExecuteInterpreter())
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
            msg += "time you use it. Please just make sure to resolve the "
            msg += "unkown error before you proceed to use this tool."
            raise UnkownError(err, msg)
        # Execute all events after linking and print them
        try:
            if not const.mode_args.skipevents and not const.mode_args.skipafter:
                interpreter = EventPrintInterpreter if const.mode_args.dryrun else EventExecInterpreter
                difflog.run_interpreter(
                    interpreter(old_state, "after")
                )
        except CustomError:
            raise
        except Exception as err:
            msg = "An unkown error occured during after_event execution."
            raise UnkownError(err, msg)

    @staticmethod
    def run_steps(args=None):
        yield "init_logger"
        UberDot.__init_logger()
        try:
            yield "create_udot"
            udot = UberDot()
            yield "parse_args"
            udot.parse_arguments(args)
            yield "perpare_path"
            sys.path.append(const.settings.profile_files)
            yield "exec_args"
            udot.execute_arguments()
            yield "crop_log"
            UberDot.crop_logfile()
            yield "fin"
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

    @staticmethod
    def crop_logfile():
        if const.settings.logfilesize > 0:
            # Read previous file
            content = []
            if os.path.exists(const.settings.logfile):
                with open(const.settings.logfile, "r") as fin:
                    content = fin.read().splitlines(True)
            # Resize log
            content = content[-const.settings.logfilesize:]
            # Write file
            with open(const.settings.logfile, "w") as fout:
                fout.writelines(content)

    @staticmethod
    def run(args=None):
        for step in UberDot.run_steps(args):
            # We are doing nothing here, since we don't want to customize
            # the execution process
            pass


class StoreDictKeyPairAction(argparse.Action):
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
        # a valid combition of arguments and mode_argss
        super().parse_args(args, namespace)
        # Then we prepare args for the actual parsing. For this we will
        # devide it by mode_argss and parse them individual.
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
        split_argv = [[]]  # This is where we store the prepared args
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
            if c.startswith("-") and not c[1:].isdigit():
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
                    # this is a new mode_args
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
        # Initialize namespace and parse until first mode_args
        result = self.parse_command(split_argv[0], subparsers.keys())
        # Parse each mode_args
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


# import IPython
# IPython.embed()
if __name__ == "__main__":
    UberDot.run()
