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
import os
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

LINEWDTH = get_terminal_size().columns  # Width of a line
DIRNAME = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))
# Global used to store success of all tests
global_fails = 0
# Global to time execution of all tests
global_time = 0
# Global to count all tests
test_nr = 0


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
    file_list = []
    for root, _, files in os.walk(environ):
        for file in files:
            file_list.append(os.path.abspath(os.path.join(root, file)))

    # Compare dir_tree against actual directory tree in environment
    for dir_name, dir_props in dir_tree.items():
        # Add environment to directory
        dir_name = os.path.normpath(os.path.join(environ, dir_name))
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
                md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
                if "content" in file_props and md5 != file_props["content"]:
                    msg = file_path + " has wrong content:\n"
                    msg += open(file_path, "rb").read().decode()
                    raise ValueError((False, msg))
                file_list.remove(file_path)
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
                file_list.remove(link_path)

    # Check if there are files left, that wasn't described by the dir_tree
    if file_list:
        msg = "Test created unexpected files:\n"
        for file in file_list:
            msg += "  " + file + "\n"
        raise ValueError((False, msg))

# Test classes
###############################################################################

class RegressionTest():
    """This is the abstract base class for all regression tests.
    It provides simple start and check functionality"""
    def __init__(self, name, cmd_args, session="default"):
        global test_nr
        self.nr = str(test_nr).rjust(2, "0")
        test_nr += 1
        if len(sys.argv) > 1 and self.nr not in sys.argv[1:]:
            # if specific test was set by commandline and this is
            # not the correct test, do nothing
            self.success = self.dummy
            self.fail = self.dummy
        verbose = ["-v"] if len(sys.argv) > 1 else []
        self.name = name
        self.cmd_args = ["python3", "../../udot.py",
                         "--config", "regressiontest.ini",
                         "--session", session] + verbose + cmd_args
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
        if len(sys.argv) > 1:
            print(output.decode(), end="")
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
            print("\033[1mCall: \033[0m" + " ".join(self.cmd_args))
            print("\033[1mEnviron: \033[0m" + self.environ)
            print()
            print("\033[1mCause: \033[0m" + str(result["cause"]))
            if "msg" in result:
                print("\033[1mError Message:\033[0m")
                print(result["msg"])
        global_fails += int(not result["success"])
        global_time += runtime_ms
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
                print("\033[1mExpected error: \033[0m" + str(cause))
                print("\033[1mActual error: \033[0m" + str(result["cause"]))
                if "msg" in result:
                    print("\033[1mError Message:\033[0m")
                    print(result["msg"])
            else:
                print('\033[92m' + " Ok" + '\033[0m', end="")
                print(runtime_str.rjust(LINEWDTH-len(self.name)-7-len(self.nr)))
        else:
            print('\033[91m\033[1m' + " FAILED" + '\033[0m', end="")
            print(runtime_str.rjust(LINEWDTH-len(self.name)-11-len(self.nr)))
            print("\033[93m\033[1mExpected error in " + phase + " did not" +
                  " occur!\033[0m")
            print("\033[1mExpected error:\033[0m " + str(cause))
        if result["success"] or result["cause"] != cause:
            global_fails += 1
        global_time += runtime_ms
        self.cleanup()
        return not result["success"]


class DirRegressionTest(RegressionTest):
    """Regression check if uberdot makes the expected
    changes to the filesystem"""
    def __init__(self, name, cmd_args, before, after, session="default"):
        super().__init__(name, cmd_args, session)
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
    def __init__(self, name, cmd_args, before, output, session="default"):
        super().__init__(name, cmd_args, session)
        self.before = before
        self.output = output

    def pre_check(self):
        try:
            dircheck(self.environ, self.before)
        except ValueError as err:
            return err.args[0]
        return True, ""

    def run_check(self, exitcode, msg, error):
        if msg.decode() != self.output:
            error = "Output was:\n" + repr(msg)
            error += "\nbut should be:\n" + repr(self.output.encode())
            return False, "Output is not as expected", error
        return True, ""

    def post_check(self):
        return True, ""


class SimpleOutputTest(OutputTest):
    def __init__(self, name, cmd_args, before, session="default"):
        super().__init__(name, cmd_args, before, None, session)

    def run_check(self, exitcode, msg, error):
        if exitcode:
            return False, "Exited with exitcode " + str(exitcode), error.decode()
        return True, ""


class InputDirRegressionTest(DirRegressionTest):
    def __init__(self, name, cmd_args, before, after, userinput, session="default"):
        super().__init__(name, cmd_args, before, after, session)
        self.input = userinput + "\n" + "\004\004"  # ctrl-d x2

    def run(self):
        env = os.environ.copy()
        env["UBERDOT_TEST"] = "1"
        master, slave = pty.openpty()
        p = Popen(self.cmd_args, stdin=slave, stdout=PIPE, stderr=PIPE, env=env)

        ticks = 0
        while p.poll() is None and ticks < 5000:
            # Wait a tick
            ticks += 1
            time.sleep(0.001)
            # Write input if process is ready
            _, w, _ = select.select([master], [master], [], 0)
            if w and self.input:
                self.input = self.input[os.write(master, self.input.encode()):]

        # Check if timeout was reached
        if ticks >= 5000:
            p.kill()
            return False, -1, "Test timed out after 5 seconds."

        output = p.stdout.read()
        error_msg = p.stderr.read()

        exitcode = p.returncode
        if len(sys.argv) > 1:
            print(output.decode(), end="")
        return self.run_check(exitcode, output, error_msg)



# Test data
###############################################################################

before = {
    ".": {
        "files": [{"name": "untouched.file"}],
    }
}

after_nooptions = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
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
                "target": "files/name1",
            },
            {
                "name": "name5",
                "target": "files/name5",
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
                "target": "files/name2",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            }
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "files/name6",
            },
            {
                "name": "name7",
                "target": "files/name7",
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
                "target": "files/name1",
            },
            {
                "name": "name5",
                "target": "files/name5",
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
                "target": "files/name2",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            }
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name6",
                "target": "files/name6",
            },
            {
                "name": "name7",
                "target": "files/name7",
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
                "target": "files/name1",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name",
                "target": "files/name2",
            },
            {
                "name": "name6",
                "target": "files/name5",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name",
                "target": "files/name3",
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
                "target": "files/name1",
            },
            {
                "name": "name2bla",
                "target": "files/name2",
            },
            {
                "name": "name5.png",
                "target": "files/name5",
            },
            {
                "name": "name6",
                "target": "files/name6",
            },
            {
                "name": "name11.png",
                "target": "files/name11.file",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
            }
        ],
    },
    "name4": {
        "links": [
            {
                "name": "test",
                "target": "files/name4",
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name",
                "target": "files/name3",
            },
            {
                "name": "filename4",
                "target": "files/name4",
            },
            {
                "name": "filename5",
                "target": "files/name5",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "encrypt8",
                "target": "data/sessions/default/dynamicfiles/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "data/sessions/default/dynamicfiles/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
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
                "target": "data/sessions/default/dynamicfiles/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt8",
                "target": "data/sessions/default/dynamicfiles/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "data/sessions/default/dynamicfiles/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
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
                "target": "data/sessions/default/dynamicfiles/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
            {
                "name": "merge3",
                "target": "data/sessions/default/dynamicfiles/merged/merge2#04b6c550264c39e8b533d7f7b977415e",
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
                "target": "data/sessions/default/dynamicfiles/piped/file#fdb6e0c029299e6aabca0963120f0fa0",
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
                "target": "data/sessions/default/dynamicfiles/merged/merge1#526f328977744debf953a2c76c2c6169",
                "content": "526f328977744debf953a2c76c2c6169"
            },
            {
                "name": "merge2",
                "target": "data/sessions/default/dynamicfiles/piped/merge2#0281651775d0a19e648acf333cabac2f",
                "content": "0281651775d0a19e648acf333cabac2f"
            }
        ],
    }
}

before_dynamicfiles_changes = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge1",
                "target": "data/sessions/dynamic_changes/dynamicfiles/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "b355af425e5c2ca153f5ce92a924fa5c"
            },
            {
                "name": "merge2",
                "target": "data/sessions/dynamic_changes/dynamicfiles/merged/merge2#6ddb4095eb719e2a9f0a3f95677d24e0",
                "content": "efdb6a5388498d59a2c55499ba5f0ad6"
            },
            {
                "name": "name_encrypt8",
                "target": "data/sessions/dynamic_changes/dynamicfiles/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "content": "a690b594a938eb682af221b92e6e9666"
            },
            {
                "name": "name_encrypt9",
                "target": "data/sessions/dynamic_changes/dynamicfiles/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "content": "90484ee28df5cf7b136a3166349bc9e4"
            },
        ],
    }
}

after_dynamicfiles_changes = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "merge3",
                "target": "data/sessions/dynamic_changes/dynamicfiles/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
            },
            {
                "name": "merge4",
                "target": "data/sessions/dynamic_changes/dynamicfiles/merged/merge2#6ddb4095eb719e2a9f0a3f95677d24e0",
            },
            {
                "name": "name_encrypt6",
                "target": "data/sessions/dynamic_changes/dynamicfiles/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
            },
            {
                "name": "name_encrypt7",
                "target": "data/sessions/dynamic_changes/dynamicfiles/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
            },
        ],
    },
    "../data/sessions/dynamic_changes/dynamicfiles/decrypted": {
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
    "../data/sessions/dynamic_changes/dynamicfiles/merged": {
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
            }
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
                "content": "48a24b70a0b376535542b996af517398"
            }
        ],
    }
}

after_event_no_before = {
    ".": {
        "files": [
            {"name": "untouched.file"},
            {
                "name": "name4",
                "content": "26ab0db90d72e28ad0ba1e22ee510510"
            },
        ],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
                "content": "48a24b70a0b376535542b996af517398"
            },
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
            {
                "name": "name5",
                "target": "files/name5",
            },
            {
                "name": "name6",
                "target": "files/name6",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "prefix_name2",
                "target": "files/name2",
            },
            {
                "name": "prefix_name3",
                "target": "files/name3",
            },
            {
                "name": "prefix_name4",
                "target": "files/name4",
            },
            {
                "name": "prefix_name5",
                "target": "files/name5",
            },
            {
                "name": "prefix_name6",
                "target": "files/name6",
            }
        ],
    }
}

after_superprofile_with_exclusion = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "prefix_name2",
                "target": "files/name2",
            },
            {
                "name": "prefix_name3",
                "target": "files/name3",
            },
            {
                "name": "prefix_name4",
                "target": "files/name4",
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/tag1%name2",
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
            {
                "name": "name5",
                "target": "files/name5",
            },
            {
                "name": "name6",
                "target": "files/name6",
            },
            {
                "name": "name11.file",
                "target": "files/name11.file",
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
                "target": "files/tag3%name5",
            },
            {
                "name": "name6",
                "target": "files/tag3%name6",
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/tag1%name2",
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
            {
                "name": "name5",
                "target": "files/tag3%name5",
            },
            {
                "name": "name6",
                "target": "files/tag3%name6",
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
                "target": "files/tag1%name2",
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
            {
                "name": "name10",
                "target": "files/tag%name10",
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
                "target": "files/name1",
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
                "target": "files/name1",
            },
            {
                "name": "file",
                "target": "files/name5",
            },
            {
                "name": "name11.file",
                "target": "files/file",
            }
        ],
    },
    "subdir": {
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
            },
            {
                "name": "name2",
                "target": "files/name2",
            }
        ],
    }
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
                "target": "files/name2"
            },
            {
                "name": "file3",
                "target": "files/name3"
            }
        ]
    },
    "subdir": {
        "links": [
            {
                "name": "file2",
                "target": "files/tag1%name2"
            },
            {
                "name": "file3",
                "target": "files/name3"
            }
        ]
    }
}


after_default = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": ".name1test",
                "target": "files/name1"
            },
            {
                "name": "name2test",
                "target": "files/tag1%name2"
            },
            {
                "name": "name6",
                "target": "files/name6"
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
                "target": "files/name1"
            },
            {
                "name": "name2",
                "target": "files/name2",
                "permission": 600
            },
            {
                "name": "name3",
                "target": "files/name3",
                "permission": 755
            },
            {
                "name": "name4",
                "target": "files/name4",
                "permission": 755
            },
            {
                "name": "name5",
                "target": "files/name5",
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
                "target": "files/name1"
            }
        ]
    }
}

after_options = {
    ".": {
        "files": [{"name": "untouched.file"}],
        "links": [
            {
                "name": "file",
                "target": "files/tag1%name2"
            },
            {
                "name": "file2",
                "target": "files/name6"
            },
            {
                "name": "testfile",
                "target": "files/name1"
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
                "target": "files/name1",
            },
            {
                "name": "name2",
                "target": "files/name2",
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
            {
                "name": "name5",
                "target": "files/name5",
            },
            {
                "name": "name6",
                "target": "files/tag1%name6",
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
                "target": "files/name5",
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
                "target": "files/name2",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name6",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
        ],
    },
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
                "target": "files/name5",
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
                "target": "files/name2",
            }
        ],
    },
    "subdir2": {
        "links": [
            {
                "name": "name7",
                "target": "files/name7",
            }
        ],
    },
    "subdir/subsubdir": {
        "links": [
            {
                "name": "name6",
                "target": "files/name3",
            },
            {
                "name": "name4",
                "target": "files/name4",
            },
        ],
    },
}

after_blacklisted = {
    ".": {
        "links":[
            {
                "name": "untouched.file",
                "target": "files/name1",
            },
        ]
    }
}

# Test execution
###############################################################################

# Setup environment
owd = os.getcwd()
os.chdir(DIRNAME)

# Fix permissions as they could change when the repo was cloned
process = Popen(["find", "-L", "(",
                 "-type", "f", "-path", "./environment*/*", "-or",
                 "-type", "f", "-path", "./files/*", "-or",
                 "-type", "f", "-path", "./profiles*/*",
                 "-not", "-name", "*.pyc", ")",
                 "-exec", "chmod", "644", "--", "{}", "+" ],
                stderr=PIPE)
_, error_msg = process.communicate()
if process.returncode:
    print(error_msg.decode())
    raise ValueError("chmoding test files failed")


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
                  ["--exclude", "Something", "update", "somenthingelse", "Something"],
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
                  ["--exclude", "Subprofile2", "--exclude", "Subprofile4", "update", "-m", "SuperProfile"],
                  before, after_superprofile_with_exclusion).success()
DirRegressionTest("Arguments: --log",
                  ["--log", "environment-default/log.txt", "update",  "-m", "DirOption"],
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
InputDirRegressionTest("Conflict: Dynamicfile was modified",
                       ["update", "DynamicFiles"],
                       before_dynamicfiles_changes, after_dynamicfiles_changes,
                       "i\nD\nu\np\n\nI\nu", "dynamic_changes").success()
DirRegressionTest("Event: On Install",
                  ["update", "SuperProfileEvent"],
                  before, after_event).success()
DirRegressionTest("Event: On Update",
                  ["update", "-f", "SuperProfileEvent"],
                  after_event, after_event_update, "event").success()
DirRegressionTest("Event: On Uninstall",
                  ["remove", "SuperProfileEvent"],
                  after_event, before, "event").success()
DirRegressionTest("Event: --skipbefore",
                  ["update", "--skipbefore", "SuperProfileEvent"],
                  before, after_event_no_before).success()
DirRegressionTest("Event: --skipafter",
                  ["update", "-f", "--skipafter", "SuperProfileEvent"],
                  after_event, after_event_no_after, "event").success()
DirRegressionTest("Event: --skipevents",
                  ["remove", "--skipevents", "SuperProfileEvent"],
                  after_event, after_event_no_event, "event").success()
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
                  after_diroptions, after_updatediroptions, "update").success()
DirRegressionTest("Update: Uninstall",
                  ["remove", "DirOption"],
                  after_diroptions, before, "update").success()
# TODO: For this test we should also check the state file
DirRegressionTest("Update: Uninstall with excludes",
                  ["--exclude", "Subprofile2", "remove", "SuperProfileTags"],
                  after_tags, after_subprofile2, "nested").success()
DirRegressionTest("Update: --parent",
                  ["update", "--parent", "SuperProfileTags", "-m", "Subprofile2", "Subprofile5"],
                  after_tags, after_parent, "nested").success()
DirRegressionTest("Update: --dui",
                  ["update", "--dui", "SuperProfileTags"],
                  after_tags, after_updatedui, "nested").success()
InputDirRegressionTest("Update: --superforce",
                       ["update", "--superforce", "OverwriteBlacklisted"],
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
                 after_diroptions, "update").success()
OutputTest("Output: find tags",
           ["find", "-t"],
           before, "tag\ntag1\ntag2\ntag3\n").success()
OutputTest("Output: find profiles",
           ["find", "-p", "Super"],
           before, "SuperProfile\nSuperProfileEvent\nSuperProfileTags\n").success()
OutputTest("Output: find dotfiles",
           ["find", "-dr", r"name\d{2}"],
           before, "name10\nname11.file\n").success()
SimpleOutputTest("Output: find all",
                 ["find", "-ptdali", "name"],
                 before).success()
DirRegressionTest("Fail: Not a profile",
                  ["update", "NotAProfileFail"],
                  before, before).fail("run", 104)
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
                  after_tags, before, "nested").fail("run", 102)
DirRegressionTest("Fail: Link moved between profiles",
                  ["update", "SuperProfileTags"],
                  after_tags, before, "nested").fail("run", 102)


# TODO: For these tests we should also check the state file
DirRegressionTest("Autofix: Take over",
                  ["--fix", "t", "show"],
                  before_modified, before_modified, "modified").success()
DirRegressionTest("Autofix: Restore",
                  ["--fix", "r", "show"],
                  before_modified, after_diroptions, "modified").success()
DirRegressionTest("Autofix: Untrack",
                  ["--fix", "u", "show"],
                  before_modified, before_modified, "modified").success()
InputDirRegressionTest("Autofix: Decide",
                       ["--fix", "d", "show"],
                       before_modified, after_modified,
                       "s\np\nu\nt\nr", "modified").success()
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
#    dynamic files changed
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
