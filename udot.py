#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This is the main module. It implements the UDot class and a short
startup script.

You can run this directly from the CLI with

.. code:: bash

    python udot.py <arguments>

or you can import UDot in another script for debugging and testing purposes.
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


# Imports from pythons standart library
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

# Coverage setup
if os.getenv("COVERAGE_PROCESS_START"):  # pragma: no cover
    import coverage
    coverage.process_startup()

# Imports from own modules
from uberdot.interpreters import *
from uberdot.differencesolver import *
from uberdot.state import State
from uberdot.state import GlobalState
from uberdot.utils import *  # This will initialize the const object
from uberdot.profile import ProfileLoader
from uberdot.dynamicfile import load_file_from_buildup

# Setup globals
const = Const()
globalstate = GlobalState()
logger = None

# Setup decorators for safe executions of functions
def critical_handler(msg):
    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                function(*args, **kwargs)
            except CustomError:
                raise
            except Exception as err:
                raise UnkownError(err, msg)
        return wrapper
    return decorator

def pokemon_handler(function):
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
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
            log_warning("The error above was unexpected. But it should be" +
                        " fine, as I did nothing critical at the time :)")
            sys.exit(100)
    return wrapper


# Main class
class UDot:
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
        UDot.__init_logger()

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

    # TODO how to reinit logger?
    @staticmethod
    def __config_logger():
        logger.setLevel(const.args.loglevel)
        if const.args.log:
            ch = NoColorFileHandler(const.settings.logfile)
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter(const.settings.logfileformat)
            ch.setFormatter(formatter)
            logger.addHandler(ch)


    #########################################################################
    # Commandline Interface
    #########################################################################

    def parse_arguments(self, *arguments):
        """Parses the commandline arguments. This function can parse a custom
        list of arguments, instead of ``sys.args``.

        Args:
            arguments (list): A list of arguments that will be parsed instead
                of ``sys.args``

        Raises:
            :class:`~errors.UserError`: One ore more arguments are invalid or
                used in an invalid combination.
        """
        if not arguments:
            arguments = sys.argv[1:]

        # Setup parser
        parser = CustomNamespaceParser()
        subparsers = parser.add_subparsers(
            parser_class=CustomNamespaceParser,
            dest="mode",
            description="For more help on the modes use 'udot.py <mode> -h'",
        )
        parser_profiles = CustomNamespaceParser(add_help=False)
        parser_profiles.add_argument(
            "-e", "--exclude",
            help="specify a profile that will be ignored for this operation",
            nargs="*"
        )
        parser_profiles.add_argument(
            "include",
            help="do everything only for this list of profiles",
            nargs="*"
        )

        # Setup top level arguments
        parser.add_argument(
            "-c", "--config",
            help="load an additional config",
            nargs="*",
            action="extend"
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
        parser_show_selection = CustomNamespaceParser(add_help=False)
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
        parser_run = CustomNamespaceParser(add_help=False)
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
            help="use Delete/Update/Insert strategy (less conflicts, worse logging)",
            action=StoreBoolAction
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
            "-a", "--searchall",
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

        # Setup mode sync arguments
        help_text = "Synchronise changes made to dotfiles back to the dotfile directory"
        parser_sync = subparsers.add_parser(
            "sync",
            description=help_text,
            help=help_text
        )
        parser_sync.add_argument(
            "files",
            help="only sync this list of files",
            nargs="*"
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
        const.load_from_args(args)

        if args.debuginfo:
            # At this point everything is loaded, so we print debuginfo
            # immediatly so no exception that might occur later on
            # won't "shadow" this output
            const.print_all()
            sys.exit(0)

        # Configure logger
        UDot.__config_logger()

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
        if hasattr(const.mode, "include"):
            profiles_included = list(set(const.mode.include) - set(const.mode.exclude))
            if sorted(profiles_included) != sorted(const.mode.include):
                msg = "You can not include and exclude a profile at the same time."
                raise UserError(msg)
        if const.args.mode == "find":
            if (not const.find.name and not const.find.filename \
                    and not const.find.content and not const.find.searchall):
                msg = "You need to set at least one of -n/-f/-c/-a."
                raise UserError(msg)

    def load_state(self):
        globalstate.load()
        self.state = globalstate.current

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
        self.load_state()
        if const.args.mode == "history":
            self._exec_history()
            return
        # Try to fix state, to make sure it matches the actual state of the filesystem
        self.fix_state()
        if const.args.mode == "show":
            self._exec_show()
        elif const.args.mode == "timewarp":
            self._exec_timewarp()
        elif const.args.mode == "remove":
            self._exec_remove()
        elif const.args.mode == "update":
            self._exec_update()
        elif const.args.mode == "resume":
            self._exec_resume()
        elif const.args.mode == "sync":
            self._exec_sync()
        else:
            raise FatalError("None of the expected modes were set.")

    def _exec_find(self):
        result = []
        nothing_selected = (not const.find.profiles and not const.find.dotfiles
                            and not const.find.tags)
        # Search for profiles
        if const.find.profiles or nothing_selected:
            result += self.find_profiles(**const.find.as_dict())

        # Search for dotfiles
        if const.find.dotfiles or nothing_selected:
            result += self.find_dotfile(**const.find.as_dict())
        # Search for tags (this only collects the tags from filenames because
        # it doesn't make sense to search in the content of files or whatever)
        if const.find.tags:
            result += self.find_tags(**const.find.as_dict())

        # Print all the results
        for file, entry in result:
            if const.find.locations:
                print(file + ": " + entry)
            else:
                print(entry)

    def _exec_help(self):
        log_debug("Starting man with local docs.")
        os.execvp("man", ["-l", abspath("docs/sphinx/build/man/uberdot.1")])

    def _exec_history(self):
        for snapshot in self.get_history():
            msg = "[" + str(snapshot[0]) + "] "
            if snapshot[1]:
                msg += const.settings.col_emph + "(current) " + const.internal.col_endc
            msg += "ID: " + snapshot[2]
            msg += "  Date: " + snapshot[3]
            msg += "  Version: " + snapshot[4]
            msg += "  Root profiles: " + " ".join(snapshot[5])
            print(msg)

    def _exec_show(self):
        """Print out the state file in a pretty format.

        Prints only the profiles specified in the commandline arguments. If
        none are specified it prints all profiles of the state file."""
        if const.show.state is not None:
            temp_state = State(const.show.state)
            for profile in temp_state.values():
                if not const.mode.include or profile["name"] in const.mode.include:
                    self.print_profile(profile, **const.show.as_dict())
        else:
            last_user = ""
            for user, profile in globalstate.get_profiles():
                # Skip users that shall not be printed
                if not const.show.allusers:
                    if const.show.users:
                        if user not in const.show.users:
                            continue
                    elif const.internal.user != user:
                        continue
                # Print the next user
                if user != last_user:
                    # But only if other users shall be shown
                    if const.show.allusers or const.show.users:
                        print(const.settings.col_emph + "User: " + const.internal.col_endc + user)
                    last_user = user
                # Show all profiles that are specified or all if none was specified
                if not const.show.include or profile["name"] in const.show.include:
                    self.print_profile(profile, **const.show.as_dict())

    def _exec_remove(self):
        log_debug("Calculating operations to remove profiles.")
        dfs = UninstallDiffSolver(self.get_profilenames(const.remove.include, const.remove.exclude), const.remove.exclude)
        dfl = dfs.solve()
        if const.args.skiproot:
            dfl.run_interpreter(SkipRootInterpreter())
        self.resolve_difflog(dfl, **const.remove.as_dict())

    def _exec_update(self):
        profile_results = self.generate_profiles(
            const.update.include, const.update.exclude, const.defaults.as_dict()
        )
        dfs = UpdateDiffSolver(profile_results, const.update.parent, const.update.exclude)
        dfl = dfs.solve()
        if const.update.dui:
            dfl.run_interpreter(DUIStrategyInterpreter())
        if const.args.skiproot:
            dfl.run_interpreter(SkipRootInterpreter())
        self.resolve_difflog(dfl, **const.update.as_dict())

    def _exec_sync(self):
        difflog = DiffLog()
        files = const.sync.files[:]
        for profile in self.state.values():
            for link in profile["links"]:
                if not files or link["path"] in files:
                    if link["buildup"]:
                        dyn_file = load_file_from_buildup(link["buildup"])
                        with open(link["path"], "rb") as file:
                            # Load an old dynamic file and write the current content to it.
                            # This will trigger the dynamic file to populate its new content
                            # back to its source(s).
                            dyn_file.content = file.read()
                        if link["path"] in files:
                            files.remove()
                        # Now we check if the dynamic file changed and eventually create operations to update the link
                        if dyn_file.getpath() != link["target"]:
                            # old_link stays the same
                            old_link = link.copy()
                            # new_link is the same as old, but points to another dynamic file and has different buildup data
                            new_link = link.copy()
                            new_link["target"] = dyn_file.getpath()
                            new_link["buildup"] = dyn_file.get_buildup_data().as_dict()
                            difflog.update_link(profile["name"], old_link, new_link)
                    else:
                        log_warning("For '" + link["path"] + "' is no buildup information available. Skipping sync...")
        if files:
            for file in files:
                log_warning("The file '" + file + "' is not an installed link and therefore won't be synchronized.")
        # TODO needs error handling
        log_success("All files successfully synchronized back.")
        if difflog:
            log("Updating links to point to recently generated files.")
            # Execute operations from difflog
            critical_handler(
                "An unkown error occured during updating synchronised files. Some " +
                "links or your state file may be corrupted. In most " +
                "cases uberdot will fix all corruptions by itself the next " +
                "time you use it. Everything that could not be updated due to this " +
                "error will be updated the next time you update their corresponding profile.",
            )(self._resolve_operations_unsafe)(difflog, force=True)

    def _exec_version(self):
        print(
            const.settings.col_emph + "Version: " +
            const.internal.col_endc + const.internal.VERSION
        )


    #########################################################################
    # Bundled functionality of uberdot
    #########################################################################

    @staticmethod
    def check_difflog_integrity(difflog, parent, force, makedirs):
        log_debug("Checking operations for errors and conflicts.")
        # These tests should be run before the other tests, because they
        # would fail anyway if these tests don't pass
        difflog.run_interpreter(
            CheckDiffsolverResultInterpreter(),
            CheckProfilesInterpreter(parent)
        )
        # Run the rest of the tests
        tests = [
            CheckLinksInterpreter(),
            CheckLinkDirsInterpreter(makedirs),
            CheckFileOverwriteInterpreter(force),
            CheckDynamicFilesInterpreter()
        ]
        difflog.run_interpreter(*tests)

    @staticmethod
    def check_difflog_files(difflog, force):
        difflog.run_interpreter(
            CheckDiffsolverResultInterpreter(
                error_type=PreconditionError
            ),
            CheckFileOverwriteInterpreter(force)
        )

    @staticmethod
    def check_difflog_blacklisted(difflog, superforce):
        difflog.run_interpreter(CheckLinkBlacklistInterpreter(superforce))

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
    def find_dotfile(searchstr="", name=False, filename=False, content=False,
                     searchall=False, regex=False, ignorecase=False, **kwargs):
        result = []
        for file in walk_dotfiles():
            # Search in names (only file basenames, without tag)
            if name or searchall:
                searchtext = os.path.basename(file)
                if const.settings.tag_separator in searchtext:
                    idx = searchtext.index(const.settings.tag_separator)
                    searchtext = searchtext[idx+1:]
                highlighted = search_text_hl(searchtext, searchstr, regex, ignorecase)
                result += [(file, item) for item in highlighted]
            # Search in filename (full paths of dotfiles)
            if filename or searchall:
                highlighted = search_text_hl(file, searchstr, regex, ignorecase)
                result += [(file, item) for item in highlighted]
            # Search in content (full content of each dotfile)
            if content or searchall:
                try:
                    searchtext = open(file).read()
                    highlighted = search_text_hl(searchtext, searchstr, regex, ignorecase)
                    result += [(file, item) for item in highlighted]
                except UnicodeDecodeError:
                    # This is not a text file (maybe an image or encrypted)
                    pass
        return result

    @staticmethod
    def find_profiles(searchstr="", name=False, filename=False, content=False,
                      searchall=False, regex=False, ignorecase=False, **kwargs):
        result = []
        # Search in filename (full paths of files in the profile directory)
        if filename or searchall:
            for file in walk_profiles():
                highlighted = search_text_hl(file, searchstr, regex, ignorecase)
                result += [(file, item) for item in highlighted]
        for pname in ProfileLoader().available_profiles():
            file = ProfileLoader().get_location(pname)
            # Search in names (class names of all available profiles)
            if name or searchall:
                highlighted = search_text_hl(pname, searchstr, regex, ignorecase)
                result += [(file, item) for item in highlighted]
            # Search in content (source code of each available profile)
            if content or searchall:
                source = ProfileLoader().get_source(pname)
                highlighted = search_text_hl(source, searchstr, regex, ignorecase)
                result += [(file, item) for item in highlighted]
        return result

    @staticmethod
    def find_tags(searchstr="", locations=False, regex=False, ignorecase=False, **kwargs):
        result = []
        tags = []
        sep = const.settings.tag_separator
        # Collect tags first
        for file in walk_dotfiles():
            name = os.path.basename(file)
            if sep in name:
                tag = name[:name.index(sep)+len(sep)-1]
                if locations:
                    highlighted = search_text_hl(tag, searchstr, regex, ignorecase)
                    result += [(file, item) for item in highlighted]
                elif tag not in tags:
                    tags.append(tag)
        for tag in tags:
            highlighted = search_text_hl(tag, searchstr, regex, ignorecase)
            result += [(file, item) for item in highlighted]
        return result

    def fix_state(self):
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
            diffsolver = StateFilesystemDiffSolver(const.mode.exclude, action=selection)
            difflog = diffsolver.solve()
            # Execute difflog. First some obligatory checks
            log_debug("Checking operations for errors and conflicts.")
            UDot.check_difflog_files(difflog, True)
            # Also allow to skip root here
            if const.args.skiproot:
                difflog.run_interpreter(SkipRootInterpreter())
            # Gain root if needed
            self.gain_root(difflog)
            # Finally execute
            critical_handler(
                "An unkown error occured when trying to fix the state " +
                "file. Your state file is probably still corrupted. " +
                "Uberdot will again try to fix the corruptions the next" +
                " time you use it. Please just make sure to to resolve " +
                "the unkown error before you proceed to use this tool."
            )(self._resolve_operations_unsafe)(difflog, force=True)

    def gain_root(self, difflog, dryrun=False):
        if not has_root_priveleges():
            log_debug("Checking if root is required.")
            if dryrun:
                root_interpreter = RootNeededInterpreter()
            else:
                root_interpreter = GainRootInterpreter()
            difflog.run_interpreter(root_interpreter)
            if not dryrun and root_interpreter.logged:
                process = Popen([sys.executable, "resume"], stdin=PIPE)
                process.communicate(self._create_resume_pickle(difflog))
                process.wait()
                return
        else:
            log_debug("uberdot was started with root priveleges.")

    def generate_profiles(self, include=[], exclude=[], options={}):
        """Imports profiles by name and executes them. """
        profiles = []
        data = {"options": options}
        # Import and create profiles
        for profilename in self.get_profilenames(include, exclude):
            if profilename in exclude:
                log_debug("'" + profilename + "' is in exclude list." +
                          " Skipping generation of profile...")
            else:
                profiles.append(ProfileLoader().get_instance(profilename, data=data))
        # And execute/generate them
        for profile in profiles:
            profile.start_generation()
        return [p.result for p in profiles]

    def get_history(self):
        result = []
        snapshot = None
        if "snapshot" in self.state.get_specials():
            snapshot = self.state.get_special("snapshot")
        for nr, file in enumerate(self.state.get_snapshots()):
            timestamp = get_timestamp_from_path(file)
            snapshot_result = [
                int(nr)+1, snapshot == timestamp, timestamp, timestamp_to_string(timestamp)
            ]
            temp_state = State.from_timestamp(timestamp)
            snapshot_result.append(temp_state.get_special("version"))
            root_profiles = filter(
                lambda x: temp_state[x]["parent"] is None,
                temp_state.keys()
            )
            snapshot_result.append(root_profiles)
            result.append(snapshot_result)
        return result

    def get_profilenames(self, include=[], exclude=[]):
        # profilenames is equal to included profiles if provided
        profilenames = include
        # Otherwise it is equal to the list of already installed root profiles
        if not profilenames:
            profilenames = [key for key, val in self.state.items() if val["parent"] is None]
            if not profilenames:
                msg = "There are no profiles installed and no profiles "
                msg += "explicitly specified to be included."
                raise UserError(msg)
        # Also all explictly excluded profiles will be removed from profilenames
        for i, profilename in enumerate(profilenames[:]):
            if profilename in exclude:
                del profilenames[i]
        return profilenames


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


    def _exec_timewarp(self):
        cst = const.timewarp
        # Get correct state file to warp to
        if cst.state:
            new_state = State.from_file(cst.state)
        elif cst.date:
            new_state = State.from_timestamp_before(cst.date)
        elif cst.earlier or cst.later:
            delta = cst.earlier if cst.earlier else -cst.later
            if "snapshot" in self.state.get_specials():
                time = int(self.state.get_special("snapshot")) - delta
            else:
                time = int(get_timestamp_now()) - delta
            new_state = State.from_timestamp_before(time)
        elif cst.first:
            new_state = State.from_index(0)
        elif cst.last:
            new_state = State.from_index(-1)
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
        if const.mode.include or const.mode.exclude:
            # State was modified only partly, so this is a completly new snapshot
            self.state.create_snapshot()
        else:
            # State was modified entirely to match new_state, so we
            # update its snapshot reference
            snapshot = get_timestamp_from_path(new_state.file)
            self.state.set_special("snapshot", snapshot)

    def _create_resume_pickle(self, difflog):
        return pickle.dumps([const, difflog])

    def print_profile(self, profile, exclude=[], users=False, allusers=False, links=False,
                      meta=False, profiles=False, **kwargs):
        """Prints a single installed profile.

        Args:
            profile (dict): The profile that will be printed
        """
        if profile["name"] in exclude:
            log_debug("'" + profile["name"] + "' is in exclude list. Skipping...")
            return
        tab = "  " if users or allusers else ""
        if profiles or (not links and not meta):
            col = const.settings.col_emph if links or meta or not profiles else ""
            profile_header = tab + col + profile["name"] + const.internal.col_endc
            if links or meta:
                profile_header += ":"
            print(profile_header)
            tab += "  "
            if meta:
                print(tab + "Installed: " + profile["installed"])
                print(tab + "Updated: " + profile["updated"])
                if profile["parent"] is not None:
                    print(tab + "Subprofile of: " + profile["parent"])
        if links or (not profiles and not meta):
            for symlink in profile["links"]:
                print(tab + symlink["path"] + "  →  " + symlink["target"])
                if meta:
                    print(
                        tab + "    Owner: " + symlink["owner"] +
                        "   Permission: " + str(symlink["permission"]) +
                        "   Secure: " + "yes" if symlink["secure"] else "no" +
                        "   Hard: " + "yes" if symlink["hard"] else "no" +
                        "   Created: " + symlink["created"] +
                        "   Modified: " + symlink["modified"]
                    )

    def _resolve_operations_unsafe(self, difflog, dryrun=False, summary=False, force=False):
        # Execute all operations of the difflog and print them
        interpreters = []
        if not dryrun:
            interpreters.append(ExecuteInterpreter(force))
        if summary:
            # This is the first interpreter so that it can print
            # the summary before the ExecuteInterpreter prints success
            interpreters.insert(0, PrintSummaryInterpreter())
        else:
            interpreters.append(PrintInterpreter())
        difflog.run_interpreter(*interpreters)

    @critical_handler("An unkown error occured during after_event execution.")
    def resolve_events_after(self, difflog, dryrun=False):
        self._resolve_events_unsafe("after", difflog, dryrun)

    @critical_handler("An unkown error occured during before_event execution.")
    def resolve_events_before(self, difflog, dryrun=False):
        self._resolve_events_unsafe("before", difflog, dryrun)

    def _resolve_events_unsafe(self, when, difflog, dryrun):
        interpreter = EventPrintInterpreter if dryrun else EventExecInterpreter
        difflog.run_interpreter(interpreter(when))

    def resolve_difflog(self, difflog, dryrun=False, debug=False, changes=False,
                        parent=None, force=False, superforce=False, makedirs=False,
                        summary=False, skipevents=False, skipbefore=False,
                        skipafter=False, **kwargs):
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
        if debug:
            difflog.run_interpreter(PrintPlainInterpreter())
            return
        elif changes:
            difflog.run_interpreter(PrintInterpreter())
            return
        elif dryrun:
            log_warning("This is just a dry-run! Nothing of the following " +
                        "is actually happening.")
        # Run integration tests on difflog
        UDot.check_difflog_integrity(difflog, parent, force, makedirs)
        # Gain root if needed
        self.gain_root(difflog, dryrun)
        # Check blacklist not until now, because the user would need confirm it
        # twice if the programm is restarted with sudo
        UDot.check_difflog_blacklisted(difflog, superforce)

        # Now the critical part begins, devided into three main tasks:
        # 1. running events before, 2. linking, 3. running events after
        # Each part is surrounded with a try-catch block that wraps every
        # exception which isn't a CustomError into UnkownError and reraises them
        # to handle them in the outer pokemon handler

        # Execute all events before linking and print them
        if not skipevents and not skipbefore:
            self.resolve_events_before(difflog, dryrun)
        else:
            log_debug("Skipping events before.")
        # We need to run some tests again because the executed event
        # might have fucked with some links
        try:
            UDot.check_difflog_files(difflog, force)
        except CustomError as err:
            # We add some additional information to the raised errors
            err._message += "This error occured because at least one of "
            err._message += "the previously executed events interfered "
            err._message += "with files that are defined by a profile."
            raise err
        # Execute operations from difflog
        critical_handler(
            "An unkown error occured during linking/unlinking. Some " +
            "links or your state file may be corrupted. In most " +
            "cases uberdot will fix all corruptions by itself the next " +
            "time you use it. Please just make sure to resolve the " +
            "unkown error before you proceed to use this tool.",
        )(self._resolve_operations_unsafe)(difflog, dryrun, summary, force)
        # Execute all events after linking and print them
        if not skipevents and not skipafter:
            self.resolve_events_after(difflog, dryrun)
        else:
            log_debug("Skipping events after.")

    @staticmethod
    @pokemon_handler
    def run_arguments(*args):
        UDot.run_arguments_unsafe(*args)

    @staticmethod
    def run_arguments_unsafe(*args):
        udot = UDot()
        udot.parse_arguments(*args)
        udot.check_arguments()
        sys.path.append(const.settings.profile_files)
        udot.execute_arguments()
        UDot.crop_logfile()


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


class CustomNamespaceParser(argparse.ArgumentParser):
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
        # a valid combition of arguments and modes
        super().parse_args(args, namespace)
        # Then we prepare args for the actual parsing. For this we will
        # devide it by modes and parse them individual.
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
        # Then we read each argument from the commandline
        for c in args:
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
                    # this is a new mode
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
        # Initialize namespace and parse until first mode
        result = self.parse_command(split_argv[0], subparsers.keys())
        # Parse each mode
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
    UDot.run_arguments()
