#!/usr/bin/env python3

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


import hashlib
import argparse
import os
import re
import sys
import pty
import select
import time
from abc import abstractmethod
from shutil import get_terminal_size
from subprocess import PIPE
from subprocess import Popen
from subprocess import TimeoutExpired


# Constants and helpers
###############################################################################

# Width of each line in the termainal emulator
LINEWDTH = get_terminal_size().columns
# Test directory (the directory of the current file)
DIRNAME = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))
# Standart password used to encrypt files
DEFAULT_PWD = "test"
# Timeout in milliseconds for tests
test_timeout_ms = 5000
# Global used to store success of all tests
global_fails = 0
# Global to time execution of all tests
global_time = 0
# Global to count all tests
test_nr = 0


parser = argparse.ArgumentParser()
parser.add_argument("-m", "--meta", default=False, action="store_true",
                    help="show meta data about tests even if successful")
parser.add_argument("-k", "--keep-files", default=False, action="store_true",
                    help="don't reset files after test")
parser.add_argument("-v", "--verbose", default=False, action="store_true",
                    help="run tests with verbose output instead of no output")
parser.add_argument("tests", nargs="*", type=int,
                    help="only perform this list of tests (referenced by number)")
args = parser.parse_args()


def dircheck(environ, dir_tree):
    """Checks if dir_tree matches the actual directory
    tree in the filesystem"""

    # Helper functions
    def check_owner(path, props, is_link=False):
        """For owner permissions we only look up if its a normal
        user or the root user because we can't create other
        users just for the sake of these tests"""
        stat = os.lstat if is_link else os.stat
        if "rootuser" not in props:
            props["rootuser"] = False
        if "rootgroup" not in props:
            props["rootgroup"] = False
        if bool(stat(path).st_uid) == props["rootuser"]:
            user = "root" if props["rootuser"] else "user"
            raise ValueError((False, path + " is a not owned by " + user))
        if bool(stat(path).st_gid) == props["rootgroup"]:
            group = "root" if props["rootgroup"] else "group"
            raise ValueError((False, path + " is a not owned by " + group))

    def check_permission(path, permission):
        perm_real = str(oct(os.stat(path).st_mode))[-3:]
        if perm_real != str(permission):
            raise ValueError((False, path + " has permission " + perm_real))

    # Collect all files/links in environment
    file_set = set()
    for root, _, files in os.walk(environ):
        for file in files:
            file_set.add(os.path.abspath(os.path.join(root, file)))

    # Compare dir_tree against actual directory tree in environment
    for dir_name, dir_props in dir_tree.items():
        # Add environment to directory
        dir_name = os.path.normpath(os.path.join(environ, dir_name))
        # Extend file_set
        if "check_full" not in dir_props or dir_props["check_full"]:
            for file in [node for node in os.listdir(dir_name) if os.path.isfile(node)]:
                file_set.add(os.path.join(dir_name, file))
        # Directory existance
        if not os.path.isdir(dir_name):
            raise ValueError((False, dir_name + " is a not a directory"))
        # Directory permission
        if "permission" in dir_props:
            check_permission(dir_name, dir_props["permission"])
        # Directory owner
        check_owner(dir_name, dir_props)
        # Files
        if "files" in dir_props:
            for file_props in dir_props["files"]:
                file_path = os.path.join(dir_name, file_props["name"])
                # File existance
                if os.path.islink(file_path) or not os.path.isfile(file_path):
                    raise ValueError((False, file_path + " is a not a file"))
                # File permission
                if "permission" in file_props:
                    check_permission(file_path, file_props["permission"])
                # File owner
                check_owner(file_path, file_props)
                # File content
                file_content = open(file_path, "rb").read()
                md5 = hashlib.md5(file_content).hexdigest()
                if "content" in file_props and md5 != file_props["content"]:
                    msg = file_path + " has wrong content:\n"
                    msg += file_content.decode()
                    raise ValueError((False, msg))
                # Decrypted file content
                if "decrypt_content" in file_props:
                    args = ["gpg", "-q", "--yes", "--batch", "--passphrase"]
                    args += [DEFAULT_PWD, "-o", file_path + ".tmp"]
                    process = Popen(args, stdin=PIPE, stderr=PIPE)
                    _, stderr = process.communicate(input=file_content)
                    if process.returncode:
                        msg = "Invoking OpenPGP failed. Error output was:\n" + stderr.decode()
                        raise ValueError((False, msg))
                    file_content = open(file_path + ".tmp", "rb").read()
                    md5 = hashlib.md5(file_content).hexdigest()
                    if md5 != file_props["decrypt_content"]:
                        msg = file_path + " has wrong content:\n"
                        msg += file_content.decode()
                        raise ValueError((False, msg))
                # Update file_set
                file_set.discard(file_path)
        # Links
        if "links" in dir_props:
            for link_props in dir_props["links"]:
                link_path = os.path.join(dir_name, link_props["name"])
                # Link existance
                if not os.path.islink(link_path):
                    raise ValueError((False, link_path + " is a not a link"))
                # Link permission
                if "permission" in link_props:
                    check_permission(link_path, link_props["permission"])
                # Link owner
                check_owner(link_path, link_props, True)
                # Link target
                target_path = os.path.normpath(
                    os.path.join(dir_name, os.readlink(link_path))
                )
                link_props["target"] = os.path.abspath(link_props["target"])
                if target_path != link_props["target"]:
                    msg = link_path + " should point to " + link_props['target']
                    msg += ", but points to " + target_path
                    raise ValueError((False, msg))
                # Link target content
                md5 = hashlib.md5(open(target_path, "rb").read()).hexdigest()
                if "content" in link_props and md5 != link_props["content"]:
                    msg = link_path + " has wrong content:\n"
                    msg += open(target_path, "rb").read().decode()
                    raise ValueError((False, msg))
                file_set.discard(link_path)

    # Check if there are files left, that wasn't described by the dir_tree
    if file_set:
        msg = "Test created unexpected files:\n"
        for file in file_set:
            msg += "  " + file + "\n"
        raise ValueError((False, msg))


# Test classes
###############################################################################

class RegressionTest():
    """This is the abstract base class for all regression tests.
    It provides simple start and check functionality"""
    def __init__(self, name, cmd_args, session="default", config=None):
        global test_nr
        self.nr = str(test_nr).rjust(2, "0")
        if args.tests and test_nr not in args.tests:
            # if specific test was set by commandline and this is
            # not the correct test, do nothing
            self.success = self.dummy
            self.fail = self.dummy
        verbose = ["-v"] if args.verbose else []
        test_nr += 1
        self.name = name
        self.cmd_args = [
            "python3", "../../udot.py", "--config", "regressiontest.ini"
        ]
        if config:
            self.cmd_args += ["--config", config + ".ini"]
        self.cmd_args += ["--session", session] + verbose + cmd_args
        self.cmd_line = "UBERDOT_TEST=1 " + " ".join(self.cmd_args)
        self.session = session
        self.environ = os.path.join(DIRNAME, "environment-" + self.session)

    def dummy(self, *args):
        """Do nothing"""

    def start(self):
        """Starts the test and runs all checks"""
        pre = self.pre_check()
        if not pre[0]:
            return {"success": False, "phase": "pre", "cause": pre[1]}
        run = self.run()
        if not run[0]:
            return {"success": False, "phase": "run", "cause": run[1], "msg": run[2]}
        post = self.post_check()
        if not post[0]:
            return {"success": False, "phase": "post", "cause": post[1]}
        return {"success": True}

    def run(self):
        """Runs the test. In this standart implementation a test is considered
        successful if uberdot terminates with exitcode 0."""
        env = os.environ.copy()
        env["UBERDOT_TEST"] = "1"
        process = Popen(self.cmd_args, stdout=PIPE, stderr=PIPE, env=env)
        try:
            output, error_msg = process.communicate(timeout=5)
        except TimeoutExpired:
            return False, -1, "Test timed out after 5 seconds."
        exitcode = process.returncode
        if args.tests:
            print(output.decode(), end="\n" if error_msg else "")
            print(error_msg.decode(), end="")
        return self.run_check(exitcode, output, error_msg)

    def run_check(self, exitcode, msg, error):
        return not exitcode, exitcode, error.decode()

    def cleanup(self):
        """Resets test environment and installed files"""
        checkouts = [
            DIRNAME + "/data/sessions/",
            DIRNAME + "/files/"
        ]
        if os.path.exists(self.environ):
            checkouts.append(self.environ)
        # Reset environment and installed dir with git
        process = Popen(["git", "checkout", "HEAD", "--"] + checkouts, stderr=PIPE)
        _, error_msg = process.communicate()
        if process.returncode:  # Exitcode is > 0, so git failed
            print(error_msg.decode())
            raise ValueError("git-checkout failed")
        process = Popen(["git", "clean", "-fdq", "--"] + checkouts, stderr=PIPE)
        _, error_msg = process.communicate()
        if process.returncode:  # Exitcode is > 0, so git failed
            print(error_msg.decode())
            raise ValueError("git-clean failed")
        # Fix permissions as they could change when the repo was cloned
        process = Popen(["find", "-L", "(",
                         "-type", "f", "-path", "./environment*/*", "-or",
                         "-type", "f", "-path", "./files/*", "-or",
                         "-type", "f", "-path", "./profiles*/*",
                         "-not", "-name", "*.pyc", ")",
                         "-exec", "chmod", "644", "--", "{}", "+" ],
                        stdout=PIPE, stderr=PIPE, cwd=DIRNAME)
        _, error_msg = process.communicate()
        if process.returncode:
            print(error_msg.decode())
            raise ValueError("Chmoding test files failed!")

    @abstractmethod
    def pre_check(self):
        """The check executed before the test to make sure the test is
        run on the correct preconditions"""

    @abstractmethod
    def post_check(self):
        """The check executed after the test to make sure the test
        behave like expected"""

    def success(self):
        """Execute this test. Expect it to be successful"""
        global global_fails, global_time
        self.cleanup()
        now = time.time()
        result = self.start()
        runtime_ms = int((time.time()-now)*1000)
        runtime_str = str(runtime_ms) + "ms"
        print(LINEWDTH*"-")
        print("\033[1m[" + self.nr + "] " + self.name + ":", end="")
        if result["success"]:
            print('\033[92m' + " Ok" + '\033[0m', end="")
            print(runtime_str.rjust(LINEWDTH-len(self.name)-7-len(self.nr)))
        else:
            print('\033[91m\033[1m' + " FAILED" + '\033[0m'
                  + " in " + result["phase"], end="")
            print(runtime_str.rjust(
                LINEWDTH-len(self.name)-len(result["phase"])-15-len(self.nr)
            ))
        if not result["success"] or args.meta:
            print("\033[1mCall: \033[0m" + self.cmd_line)
            print("\033[1mEnviron: \033[0m" + self.environ)
        if not result["success"]:
            print()
            print("\033[1mCause: \033[0m" + str(result["cause"]))
            if "msg" in result:
                print("\033[1mError Message:\033[0m")
                print(result["msg"])
        global_fails += int(not result["success"])
        global_time += runtime_ms
        if not args.keep_files:
            self.cleanup()
        return result["success"]

    def fail(self, phase, cause):
        """Execute this test. Expect a certain error"""
        global global_fails, global_time
        self.cleanup()
        now = time.time()
        result = self.start()
        runtime_ms = int((time.time()-now)*1000)
        runtime_str = str(runtime_ms) + "ms"
        print(LINEWDTH*"-")
        print("\033[1m[" + self.nr + "] " + self.name + ":", end="")
        if not result["success"]:
            if result["cause"] != cause:
                print('\033[91m\033[1m' + " FAILED" + '\033[0m', end="")
                print(runtime_str.rjust(LINEWDTH-len(self.name)-11-len(self.nr)))
            else:
                print('\033[92m' + " Ok" + '\033[0m', end="")
                print(runtime_str.rjust(LINEWDTH-len(self.name)-7-len(self.nr)))
            if result["cause"] != cause or args.meta:
                print("\033[1mCall: \033[0m" + self.cmd_line)
                print("\033[1mEnviron: \033[0m" + self.environ)
            if result["cause"] != cause:
                print()
                print("\033[1mExpected error: \033[0m" + str(cause))
                print("\033[1mActual error: \033[0m" + str(result["cause"]))
                if "msg" in result:
                    print("\033[1mError Message:\033[0m")
                    print(result["msg"])
        else:
            print('\033[91m\033[1m' + " FAILED" + '\033[0m', end="")
            print(runtime_str.rjust(LINEWDTH-len(self.name)-11-len(self.nr)))
            print("\033[1mCall: \033[0m" + self.cmd_line)
            print("\033[1mEnviron: \033[0m" + self.environ)
            print()
            print("\033[93m\033[1mExpected error in " + phase + " did not" +
                  " occur!\033[0m")
            print("\033[1mExpected error:\033[0m " + str(cause))
        if result["success"] or result["cause"] != cause:
            global_fails += 1
        global_time += runtime_ms
        if not args.keep_files:
            self.cleanup()
        return not result["success"]


class DirRegressionTest(RegressionTest):
    """Regression check if uberdot makes the expected
    changes to the filesystem"""
    def __init__(self, name, cmd_args, before, after, session="default", config=None):
        super().__init__(name, cmd_args, session, config)
        self.before = before
        self.after = after

    def pre_check(self):
        try:
            dircheck(self.environ, self.before)
        except ValueError as err:
            return err.args[0]
        return True, ""

    def post_check(self):
        try:
            dircheck(self.environ, self.after)
        except ValueError as err:
            return err.args[0]
        return True, ""


class OutputTest(RegressionTest):
    """Regression tests for output."""
    def __init__(self, name, cmd_args, before, output, session="default", config=None):
        super().__init__(name, cmd_args, session, config)
        self.before = before
        self.output = output

    def pre_check(self):
        try:
            dircheck(self.environ, self.before)
        except ValueError as err:
            return err.args[0]
        return True, ""

    def run_check(self, exitcode, msg, error):
        if exitcode:
            return False, "Exited with exitcode " + str(exitcode), error.decode()
        if msg.decode() != self.output:
            error = "Output was:\n" + repr(msg)
            error += "\nbut should be:\n" + repr(self.output.encode())
            return False, "Output is not as expected", error
        return True, ""

    def post_check(self):
        return True, ""


class RegexOutputTest(RegressionTest):
    def __init__(self, name, cmd_args, before, regex, session="default", config=None):
        super().__init__(name, cmd_args, session, config)
        self.before = before
        self.regex = regex

    def pre_check(self):
        try:
            dircheck(self.environ, self.before)
        except ValueError as err:
            return err.args[0]
        return True, ""

    def run_check(self, exitcode, msg, error):
        if exitcode:
            return False, "Exited with exitcode " + str(exitcode), error.decode()
        if not re.fullmatch(self.regex, msg.decode(), flags=re.M | re.S):
            error = "Output was:\n" + repr(msg)
            error += "\nbut should match pattern:\n" + repr(self.regex.encode())
            return False, "Output doesn't match the expected pattern.", error
        return True, ""

    def post_check(self):
        return True, ""


class SimpleOutputTest(OutputTest):
    def __init__(self, name, cmd_args, before, session="default", config=None):
        super().__init__(name, cmd_args, before, None, session, config)

    def run_check(self, exitcode, msg, error):
        if exitcode:
            return False, "Exited with exitcode " + str(exitcode), error.decode()
        return True, ""


class InputDirRegressionTest(DirRegressionTest):
    def __init__(self, name, cmd_args, before, after, userinput, session="default", config=None):
        super().__init__(name, cmd_args, before, after, session, config)
        self.input = userinput + "\n" + "\004\004"  # ctrl-d x2

    def run(self):
        env = os.environ.copy()
        env["UBERDOT_TEST"] = "1"
        master, slave = pty.openpty()
        p = Popen(self.cmd_args, stdin=slave, stdout=PIPE, stderr=PIPE, env=env)

        ticks = 0
        while p.poll() is None and ticks < test_timeout_ms:
            # Wait a tick
            ticks += 1
            time.sleep(0.001)
            # Write input if process is ready
            _, w, _ = select.select([master], [master], [], 0)
            if w and self.input:
                try:
                    idx = self.input.index("\n")
                    line = self.input[:idx]
                    self.input = self.input[idx+1:]
                except ValueError:
                    line = self.input[:]
                    self.input = ""
                line = (line + "\n").encode()
                os.write(master, line)

        # Check if timeout was reached
        if ticks >= test_timeout_ms:
            p.kill()
            return False, -1, "Test timed out after 5 seconds."

        output = p.stdout.read()
        error_msg = p.stderr.read()

        exitcode = p.returncode
        if len(args.tests):
            print(output.decode(), end="")
        return self.run_check(exitcode, output, error_msg)



# Test data
###############################################################################

before = {
    ".": {
        "files": [{"name": "untouched.file"}],
    }
}

before_update = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/update/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
                "permission": 644
            },
            {
                "name": "name5",
                "target": "data/sessions/update/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/update/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/update/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/update/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/update/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "data/sessions/update/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name7",
                "target": "data/sessions/update/files/static/name7#84bc3da1b3e33a18e8d5e1bdd7a18d7a",
            }
        ],
    }
}

before_event_update = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "456dc30f21eb07c88257f4aabb0d946f"
            },
            {
                "name": "name4",
                "content": "26ab0db90d72e28ad0ba1e22ee510510"
            },
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/event/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/event/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/event/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
        ],
    }
}

before_nested = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/nested/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/nested/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50",
            },
            {
                "name": "name3",
                "target": "data/sessions/nested/files/static/tag2%name3#2f203ac40e91f94eb0e875e242a5c7f8",
            },
            {
                "name": "name4",
                "target": "data/sessions/nested/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name5",
                "target": "data/sessions/nested/files/static/tag3%name5#dff127846c93b264011d239840d81e38",
            },
            {
                "name": "name6",
                "target": "data/sessions/nested/files/static/tag3%name6#7ba23c2e844866b2846b1b79331f48ec",
            }
        ],
    }
}

before_modified = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "files/name3",
            },
            {
                "name": "name5",
                "target": "data/sessions/modified/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "files/name11.file",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/modified/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name6",
                "target": "data/sessions/modified/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/modified/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
}


after_nooptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            }
        ],
    }
}

after_diroptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/default/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name7",
                "target": "data/sessions/default/files/static/name7#84bc3da1b3e33a18e8d5e1bdd7a18d7a",
            }
        ],
    }
}


after_logging = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {"name": "log.txt"}
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/default/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name7",
                "target": "data/sessions/default/files/static/name7#84bc3da1b3e33a18e8d5e1bdd7a18d7a",
            }
        ],
    }
}

after_nameoptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            }
       ],
    }
}

after_prefixsuffixoptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": ".name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2bla",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name5.png",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name11.png",
                "target": "data/sessions/default/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            }
        ],
    },
    "name4": {
        "links": [
            {
                "name": "test",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    }
}

after_links = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "filename4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "filename5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
       ],
    },
    "subdir": {
        "links": [
            {
                "name": "encrypt8",
                "target": "data/sessions/default/files/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "data/sessions/default/files/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            }
        ],
    }
}

after_decrypt = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name_encrypt8",
                "target": "data/sessions/default/files/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt8",
                "target": "data/sessions/default/files/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "data/sessions/default/files/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            }
        ],
    }
}

after_merge = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge1",
                "target": "data/sessions/default/files/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
            {
                "name": "merge3",
                "target": "data/sessions/default/files/merged/merge2#04b6c550264c39e8b533d7f7b977415e",
                "content": "04b6c550264c39e8b533d7f7b977415e"
            }
        ],
    }
}

after_pipe = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "file",
                "target": "data/sessions/default/files/piped/file#fdb6e0c029299e6aabca0963120f0fa0",
                "content": "fdb6e0c029299e6aabca0963120f0fa0"
            }
        ],
    }
}

after_nesteddynamic = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge1",
                "target": "data/sessions/default/files/merged/merge1#526f328977744debf953a2c76c2c6169",
                "content": "526f328977744debf953a2c76c2c6169"
            },
            {
                "name": "merge2",
                "target": "data/sessions/default/files/piped/merge2#0281651775d0a19e648acf333cabac2f",
                "content": "0281651775d0a19e648acf333cabac2f"
            }
        ],
    }
}

before_dynamicfiles_changes = {
    "../files/": {
        "check_full": False,
        "files": [
            {
                "name": "name1",
                "content": "b026324c6904b2a9cb4b88d6d61c81d1"
            },
            {
                "name": "name2",
                "content": "26ab0db90d72e28ad0ba1e22ee510510"
            },
            {
                "name": "split1",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split2",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "split3",
                "content": "26a5e8faf6e6b71cf84f7689e3819bc8"
            },
            {
                "name": "split4",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split5",
                "content": "26a5e8faf6e6b71cf84f7689e3819bc8"
            },
            {
                "name": "split6",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "split7",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split8",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "name_encrypt9",
                "content": "11ed221bd25489f76b1536dc71d848c7",
                "decrypt_content": "e59ab101cf09636fc06d10bf3d56a5cc"
            },
        ]
    },
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge1",
                "target": "data/sessions/dynamic_changes/files/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "b355af425e5c2ca153f5ce92a924fa5c"
            },
            {
                "name": "merge2",
                "target": "data/sessions/dynamic_changes/files/merged/merge2#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "efdb6a5388498d59a2c55499ba5f0ad6"
            },
            {
                "name": "merge3",
                "target": "data/sessions/dynamic_changes/files/merged/merge3#59ad5fc961d51b074abe515838c7b47f",
                "content": "2585a17a26d0afb3f9121f625e9749cb"
            },
            {
                "name": "merge4",
                "target": "data/sessions/dynamic_changes/files/merged/merge4#55ec724b6ab145d7d10b96e3c41826d3",
                "content": "55ec724b6ab145d7d10b96e3c41826d3"
            },
            {
                "name": "merge5",
                "target": "data/sessions/dynamic_changes/files/merged/merge5#e202be9c7638739cf3dabcde54f5eb38",
                "content": "8d32abd48f2d0a961dd1ac1cb1aa7639"
            },
            {
                "name": "name_encrypt8",
                "target": "data/sessions/dynamic_changes/files/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "a690b594a938eb682af221b92e6e9666"
            },
        ],
    }
}

after_dynamicfiles_changes = {
    "../files/": {
        "check_full": False,
        "files": [
            {
                "name": "name1",
                "content": "c7278e33ef0f4aff88da10dfeeaaae7a"
            },
            {
                "name": "name2",
                "content": "7f13295dbfa8c0d21c7b086699f738c3"
            },
            {
                "name": "split1",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split2",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "split3",
                "content": "26a5e8faf6e6b71cf84f7689e3819bc8"
            },
            {
                "name": "split4",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split5",
                "content": "26a5e8faf6e6b71cf84f7689e3819bc8"
            },
            {
                "name": "split6",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "split7",
                "content": "995c024029afbac98e6452118d215c5a"
            },
            {
                "name": "split8",
                "content": "1359034cba6723da2eb0d89a715467ec"
            },
            {
                "name": "name_encrypt9",
                "decrypt_content": "e59ab101cf09636fc06d10bf3d56a5cc"
            },
        ]
    },
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge3",
                "target": "data/sessions/dynamic_changes/files/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
            },
            {
                "name": "merge4",
                "target": "data/sessions/dynamic_changes/files/merged/merge2#6ddb4095eb719e2a9f0a3f95677d24e0",
            },
            {
                "name": "name_encrypt6",
                "target": "data/sessions/dynamic_changes/files/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
            },
            {
                "name": "name_encrypt7",
                "target": "data/sessions/dynamic_changes/files/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
            },
        ],
    },
    "../data/sessions/dynamic_changes/files/decrypted": {
        "files": [
            {
                "name": "name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "a690b594a938eb682af221b92e6e9666"
            },
            {
                "name": "name_encrypt8#d6eb32081c822ed572b70567826d9d9d.bak",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc.bak",
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            },
            {
                "name": "name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            },
        ]
    },
    "../data/sessions/dynamic_changes/files/merged": {
        "files": [
            {"name": "merge1#6ddb4095eb719e2a9f0a3f95677d24e0.patch"},
            {
                "name": "merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "b355af425e5c2ca153f5ce92a924fa5c"
            },
            {
                "name": "merge1#6ddb4095eb719e2a9f0a3f95677d24e0.bak",
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
            {
                "name": "merge2#6ddb4095eb719e2a9f0a3f95677d24e0.bak",
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
            {
                "name": "merge2#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
        ]
    }
}

after_event = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "456dc30f21eb07c88257f4aabb0d946f"
            },
            {
                "name": "name4",
                "content": "26ab0db90d72e28ad0ba1e22ee510510"
            },
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
        ],
    }
}

after_event_update = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "d798c3f454568f2eb88073ae85c3aa8d"
            }
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/event/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/event/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/event/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/event/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    }
}

after_event_no_before = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "5c4b252c59f7dca4166a19e95040b850"
            },
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/event/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/event/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/event/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/event/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    }
}

after_event_no_after = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "ceadf84074351d4a23c89ab94832995d"
            },
        ],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/event/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/event/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/event/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/event/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    }
}

after_event_no_event = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "test.file",
                "content": "456dc30f21eb07c88257f4aabb0d946f"
            },
            {
                "name": "name4",
                "target": "files/name4",
                "content": "26ab0db90d72e28ad0ba1e22ee510510"
            },
        ],
    }
}

after_superprofile = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
        ],
    },
    "subdir": {
        "links": [

            {
                "name": "prefix_name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "prefix_name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "prefix_name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "prefix_name5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "prefix_name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
       ],
    }
}

after_superprofile_with_exclusion = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "prefix_name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "prefix_name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "prefix_name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            }
        ],
    }
}

after_parent = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/nested/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/nested/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50",
            },
            {
                "name": "name3",
                "target": "data/sessions/nested/files/static/tag2%name3#2f203ac40e91f94eb0e875e242a5c7f8",
            },
            {
                "name": "name4",
                "target": "data/sessions/nested/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name5",
                "target": "data/sessions/nested/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name6",
                "target": "data/sessions/nested/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/nested/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            },
        ],
    }
}

after_subprofile2 = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name5",
                "target": "data/sessions/nested/files/static/tag3%name5#dff127846c93b264011d239840d81e38",
            },
            {
                "name": "name6",
                "target": "data/sessions/nested/files/static/tag3%name6#7ba23c2e844866b2846b1b79331f48ec",
            }
        ],
    }
}

after_tags = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/tag2%name3#2f203ac40e91f94eb0e875e242a5c7f8",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name5",
                "target": "data/sessions/default/files/static/tag3%name5#dff127846c93b264011d239840d81e38",
            },
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/tag3%name6#7ba23c2e844866b2846b1b79331f48ec",
            }
        ],
    }
}

after_optional = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50",
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/tag2%name3#2f203ac40e91f94eb0e875e242a5c7f8",
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name10",
                "target": "data/sessions/default/files/static/tag%name10#f92acffc479a037fdea29190230ab8b6",
            }
        ],
    }
}

after_skiproot = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            }
        ],
    }
}

after_updatediroptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/update/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
                "permission": 755
            },
            {
                "name": "file",
                "target": "data/sessions/update/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/update/files/static/file#a28cb6e1b2f194a4e2dcb523c055d7aa",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/update/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/update/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
        ],
    }
}

after_updatediroptions_alt = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name11.file",
                "target": "data/sessions/update/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name5",
                "target": "data/sessions/update/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/update/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "4name4",
                "target": "data/sessions/update/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
}

# This dirtree works only with environment-default
after_extlink = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "test1",
                "target": "environment-default/untouched.file"
            }
        ]
    },
    "test2": {
        "links": [
            {
                "name": "untouched.file",
                "target": "environment-default/untouched.file"
            }
        ]
    }
}

after_replace = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "file2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "file3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
       ]
    },
    "subdir": {
        "links": [
            {
                "name": "file2",
                "target": "data/sessions/default/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50"
            },
            {
                "name": "file3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
        ]
    }
}


after_default = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": ".name1test",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1"
            },
            {
                "name": "name2test",
                "target": "data/sessions/default/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50"
            },
            {
                "name": "name6",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1"
            }
        ]
    }
}


after_permission = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/default/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
                "permission": 600
            },
            {
                "name": "name3",
                "target": "data/sessions/default/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
                "permission": 777
            },
            {
                "name": "name4",
                "target": "data/sessions/default/files/static/name4#48a24b70a0b376535542b996af517398",
                "permission": 777
            },
            {
                "name": "name5",
                "target": "data/sessions/default/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            }
        ]
    }
}


after_ignorefiles = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
        ]
    }
}

after_options = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "file",
                "target": "data/sessions/default/files/static/tag1%name2#7453d97cd70ab49510f074ae71258d50"
            },
            {
                "name": "file2",
                "target": "data/sessions/default/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1"
            },
            {
                "name": "testfile",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1"
            }
        ]
    },
}

after_updatedui = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/nested/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name2",
                "target": "data/sessions/nested/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
            {
                "name": "name3",
                "target": "data/sessions/nested/files/static/tag2%name3#2f203ac40e91f94eb0e875e242a5c7f8",
            },
            {
                "name": "name4",
                "target": "data/sessions/nested/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name5",
                "target": "data/sessions/nested/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name6",
                "target": "data/sessions/nested/files/static/tag1%name6#1933adda42ba93cb33f100d9bd8d2f8f",
            }
        ],
    }
}

after_modified = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "files/name3",
            },
            {
                "name": "name5",
                "target": "data/sessions/modified/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "files//name11.file",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/modified/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name7",
                "target": "data/sessions/modified/files/static/name7#84bc3da1b3e33a18e8d5e1bdd7a18d7a",
            },
            {
                "name": "name6",
                "target": "data/sessions/modified/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name4",
                "target": "data/sessions/modified/files/static/name4#48a24b70a0b376535542b996af517398",
            },
            {
                "name": "name6",
                "target": "data/sessions/modified/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
        ],
    },
}

after_modified_restore = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "data/sessions/modified/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
            {
                "name": "name5",
                "target": "data/sessions/modified/files/static/name5#1dcca23355272056f04fe8bf20edfce0",
            },
            {
                "name": "name11.file",
                "target": "data/sessions/modified/files/static/name11.file#d41d8cd98f00b204e9800998ecf8427e",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name2",
                "target": "data/sessions/modified/files/static/name2#26ab0db90d72e28ad0ba1e22ee510510",
            },
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "data/sessions/modified/files/static/name3#6d7fce9fee471194aa8b5b6e47267f03",
            },
            {
                "name": "name4",
                "target": "data/sessions/modified/files/static/name4#48a24b70a0b376535542b996af517398",
            },
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "data/sessions/modified/files/static/name6#9ae0ea9e3c9c6e1b9b6252c8395efdc1",
            },
            {
                "name": "name7",
                "target": "data/sessions/modified/files/static/name7#84bc3da1b3e33a18e8d5e1bdd7a18d7a",
            }
        ],
    }
}

after_blacklisted = {
    ".": {
        "links":[
            {
                "name": "untouched.file",
                "target": "data/sessions/default/files/static/name1#b026324c6904b2a9cb4b88d6d61c81d1",
            },
        ]
    }
}

# Test execution
###############################################################################

# Setup environment
owd = os.getcwd()
os.chdir(DIRNAME)


DirRegressionTest("Simple",
                  ["update", "NoOptions"],
                  before, after_nooptions).success()
DirRegressionTest("Arguments: No mode",
                  ["NoOptions"],
                  before, before).fail("run", 101)
DirRegressionTest("Arguments: Wrong mode",
                  ["remove", "--parent", "NameOption", "NoOptions"],
                  before, before).fail("run", 101)
DirRegressionTest("Arguments: No profiles",
                  ["update"],
                  before, before).fail("run", 101)
DirRegressionTest("Arguments: Excluded and included same profile",
                  ["update", "--exclude", "Something", "--", "somenthingelse", "Something"],
                  before, before).fail("run", 101)
DirRegressionTest("Arguments: No makedirs",
                  ["update", "Links"],
                  before, before).fail("run", 103)
DirRegressionTest("Arguments: No sudo",
                  ["update", "NeedsRootConflict"],
                  before, before).fail("run", 101)
DirRegressionTest("Arguments: --skiproot",
                  ["--skiproot", "update", "NeedsRootConflict"],
                  before, after_skiproot).success()
DirRegressionTest("Arguments: --option",
                  [
                      "update", "--option", "name=file", "prefix=test",
                      "tags=tag1,notag", "--", "OptionArgument"
                  ], before, after_options).success()
DirRegressionTest("Arguments: --exclude",
                  ["update", "--exclude", "Subprofile2", "Subprofile4", "-m", "SuperProfile"],
                  before, after_superprofile_with_exclusion).success()
DirRegressionTest("Arguments: --log",
                  ["--log", "update",  "-m", "DirOption"],
                  before, after_logging).success()
DirRegressionTest("Option: name",
                  ["update", "-m", "NameOption"],
                  before, after_nameoptions).success()
DirRegressionTest("Option: directory",
                  ["update", "-m", "DirOption"],
                  before, after_diroptions).success()
DirRegressionTest("Option: prefix suffix extension",
                  ["update", "-m", "PrefixSuffixExtensionOption"],
                  before, after_prefixsuffixoptions).success()
DirRegressionTest("Option: optional",
                  ["update", "OptionalOption"],
                  before, after_optional).success()
DirRegressionTest("Option: replace",
                  ["update", "-m", "ReplaceOption"],
                  before, after_replace).success()
DirRegressionTest("Option: permission",
                  ["update", "-m", "PermissionOption"],
                  before, after_permission).success()
SimpleOutputTest("Option: environment vars",
                 ["update", "-m", "EnvironmentSubstitution"],
                 before).success()
DirRegressionTest("Command: links()",
                  ["update", "-m", "Links"],
                  before, after_links).success()
DirRegressionTest("Command: decrypt()",
                  ["update", "Decrypt"],
                  before, after_decrypt).success()
DirRegressionTest("Command: merge()",
                  ["update", "Merge"],
                  before, after_merge).success()
DirRegressionTest("Command: pipe()",
                  ["update", "Pipe"],
                  before, after_pipe).success()
DirRegressionTest("Command: Nested dynamicfiles",
                  ["update", "NestedDynamicFile"],
                  before, after_nesteddynamic).success()
DirRegressionTest("Command: subprof()",
                  ["update", "-m", "SuperProfile"],
                  before, after_superprofile).success()
DirRegressionTest("Command: tags()",
                  ["update", "SuperProfileTags"],
                  before, after_tags).success()
DirRegressionTest("Command: extlink()",
                  ["update", "-m", "ExteranalLink"],
                  before, after_extlink).success()
DirRegressionTest("Command: default()",
                  ["update", "Default"],
                  before, after_default).success()
DirRegressionTest("Command: .dotignore",
                  ["update", "IgnoreFiles"],
                  before, after_ignorefiles).success()
DirRegressionTest("Conflict: Same profile linked twice",
                  ["update", "SameProfileConflict"],
                  before, before).fail("run", 102)
DirRegressionTest("Conflict: Same profile linked twice in subprofile",
                  ["update", "SameProfileConflict2"],
                  before, before).fail("run", 102)
DirRegressionTest("Conflict: Same link created twice",
                  ["update", "SameLinkConflict"],
                  before, before).fail("run", 102)
DirRegressionTest("Conflict: Link has multiple targets",
                  ["update", "MultipleTargetsConflict"],
                  before, before).fail("run", 102)
DirRegressionTest("Conflict: Link already installed by another user",
                  ["update", "-m", "DirOption"],
                  before, before, "users").fail("run", 102)
DirRegressionTest("Conflict: DynamicFile modified",
                  ["update", "DynamicFiles"],
                  before_dynamicfiles_changes, after_dynamicfiles_changes,
                  "dynamic_changes").fail("run", 103)
DirRegressionTest("Sync",
                  ["sync"],
                  before_dynamicfiles_changes, after_dynamicfiles_changes,
                  "dynamic_changes").success()
DirRegressionTest("Event: On Install",
                  ["update", "SuperProfileEvent"],
                  before, after_event).success()
DirRegressionTest("Event: On Update",
                  ["update", "-f", "SuperProfileEvent"],
                  before_event_update, after_event_update, "event").success()
DirRegressionTest("Event: On Uninstall",
                  ["remove", "SuperProfileEvent"],
                  before_event_update, before, "event").success()
DirRegressionTest("Event: --skipbefore",
                  ["update", "-f", "--skipbefore", "SuperProfileEvent"],
                  before_event_update, after_event_no_before, "event").success()
DirRegressionTest("Event: --skipafter",
                  ["update", "-f", "--skipafter", "SuperProfileEvent"],
                  before_event_update, after_event_no_after, "event").success()
DirRegressionTest("Event: --skipevents",
                  ["remove", "--skipevents", "SuperProfileEvent"],
                  before_event_update, after_event_no_event, "event").success()
DirRegressionTest("Event: Conflicts with linking",
                  ["update", "ConflictProfileEvent"],
                  before, before).fail("run", 103)
DirRegressionTest("Event: Fail on purpose",
                  ["update", "FailProfileEvent"],
                  before, before).fail("run", 107)
DirRegressionTest("Event: Fail on error",
                  ["update", "--skipbefore", "FailProfileEvent"],
                  before, after_ignorefiles).fail("run", 107)
DirRegressionTest("Event: Fail on timeout",
                  ["update", "TimeoutProfileEvent"],
                  before, before).fail("run", 107)
DirRegressionTest("Update: Simple",
                  ["update", "-m", "DirOption"],
                  before_update, after_updatediroptions, "update").success()
DirRegressionTest("Update: Replaced and removed",
                  ["update", "DirOption"],
                  before_update, after_updatediroptions_alt, "update", "update_alt").success()
DirRegressionTest("Update: Uninstall",
                  ["remove", "DirOption"],
                  before_update, before, "update").success()
# TODO: For this test we should also check the state file
DirRegressionTest("Update: Uninstall with excludes",
                  ["remove", "--exclude", "Subprofile2", "--", "SuperProfileTags"],
                  before_nested, after_subprofile2, "nested").success()
DirRegressionTest("Update: --parent",
                  ["update", "--parent", "SuperProfileTags", "-m", "Subprofile2", "Subprofile5"],
                  before_nested, after_parent, "nested").success()
DirRegressionTest("Update: --dui",
                  ["update", "--dui", "SuperProfileTags"],
                  before_nested, after_updatedui, "nested").success()
InputDirRegressionTest("Update: --superforce",
                       ["update", "--superforce", "-f", "OverwriteBlacklisted"],
                       before, after_blacklisted, "YES").success()
SimpleOutputTest("Output: --changes",
                 ["update", "--changes", "NoOptions"],
                 before).success()
SimpleOutputTest("Output: --debug",
                 ["update", "--debug", "NoOptions"],
                 before).success()
SimpleOutputTest("Output: --dryrun normal",
                 ["update", "-d", "NoOptions"],
                 before).success()
SimpleOutputTest("Output: --dryrun with events",
                 ["update", "-d", "SuperProfileEvent"],
                 before).success()
SimpleOutputTest("Output: --summary",
                 ["--summary", "update", "NoOptions"],
                 before).success()
SimpleOutputTest("Output: --debuginfo",
                 ["--debuginfo", "version"],
                 before).success()
SimpleOutputTest("Output: show",
                 ["show", "-ampl"],
                 before_update, "update").success()
SimpleOutputTest("Output: show other state",
                 ["show", "--state", "1"],
                 before_update, "update").success()
SimpleOutputTest("Output: history",
                 ["history"],
                 before_update, "update").success()
OutputTest("Output: find tags",
           ["find", "-tn"],
           before, "tag1\ntag2\ntag3\ntag\n", config="output_tests").success()
RegexOutputTest(
    "Output: find profiles",
    ["find", "-pn", "Super"],
    before,
    r"No loading mechanism for file '.+test/regression/profiles/not_a_profile\.txt'" +
    r" available\..*SuperProfile\nSuperProfileEvent\nSuperProfileTags\n",
    config="output_tests").success()
OutputTest("Output: find dotfiles",
           ["find", "-dnr", r"name\d{2}"],
           before, "name11.file\nname10\n", config="output_tests").success()
# TODO: Use a RegexOutputTest here
SimpleOutputTest("Output: find all",
                 ["find", "-ptdali", "name"],
                 before).success()
# DirRegressionTest("Timewarp: --state number",
#                   ["timewarp", "--state", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --state path",
#                   ["timewarp", "--state", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --state timestamp",
#                   ["timewarp", "--state", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --earlier",
#                   ["timewarp", "--state", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --later",
#                   ["timewarp", "--state", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --date",
#                   ["timewarp", "--date", "", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --first",
#                   ["timewarp", "--first", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: --last",
#                   ["timewarp", "--last", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: partly",
#                   ["timewarp", "--last", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
# DirRegressionTest("Timewarp: partly with exclude",
#                   ["timewarp", "--last", "SuperProfileTags"],
#                   after_tags, after_updatedui, "warped").success()
DirRegressionTest("Fail: Not a profile",
                  ["update", "NotAProfileFail"],
                  before, before).fail("run", 103)
DirRegressionTest("Fail: Profile does not exist",
                  ["update", "ThisDoesNotExist"],
                  before, before).fail("run", 103)
DirRegressionTest("Fail: Overwrite blacklisted file",
                  ["update", "-f", "OverwriteBlacklisted"],
                  before, before).fail("run", 102)
DirRegressionTest("Fail: Recursive profile",
                  ["update", "RecursiveProfile"],
                  before, before).fail("run", 104)
DirRegressionTest("Fail: Cycle in profile",
                  ["update", "CycleProfile1"],
                  before, before).fail("run", 104)
DirRegressionTest("Fail: Link moved between profiles",
                  ["update", "SuperProfileTags"],
                  before_nested, before, "nested").fail("run", 102)
# TODO: For these tests we should also check the state file
DirRegressionTest("Autofix: Take over",
                  ["--fix", "t", "show"],
                  before_modified, before_modified, "modified").success()
DirRegressionTest("Autofix: Restore",
                  ["--fix", "r", "show"],
                  before_modified, after_modified_restore, "modified").success()
DirRegressionTest("Autofix: Untrack",
                  ["--fix", "u", "show"],
                  before_modified, before_modified, "modified").success()
InputDirRegressionTest("Autofix: Decide",
                       ["show"],
                       before_modified, after_modified,
                       "d\ns\np\nu\nt\nr\nr", "modified").success()
DirRegressionTest("Upgrade", ["show"],
                  after_tags, after_tags, "upgrade").success()

# Overall result
print(LINEWDTH*"=")
if global_fails:
    msg = str(global_fails) + " \033[1mTests \033[91mFAILED\033[0m"
else:
    msg = "\033[1mTests \033[92msuccessful\033[0m"
print(msg, end="")
print((str(round(global_time/1000, 2)) + "s").rjust(LINEWDTH-len(msg)+13))

# Exit
os.chdir(owd)
sys.exit(global_fails)



###############################################################################
# TODO: Write tests
# Already possible
#    various generation errors
# Requires testing with root
#    option secure
#    option owner
#    gain root
#    event demote()
# Not sure if possible, but still missing
#    file overwrites
#    profile overwrites
#    directory of a profile is always expanded and normalized
#    various errors in profile
