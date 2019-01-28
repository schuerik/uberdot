#!/usr/bin/env python3
"""This module provides all functionality and base classes for
regression tests. It provides also all needed types and colors
as the test modules shall be independent from Dotmanager"""

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

import hashlib
import os
import sys
from abc import abstractmethod
from shutil import rmtree
from subprocess import PIPE
from subprocess import Popen
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

# Types
###############################################################################
TestResult = Dict[str, Union[bool, str]]
CheckResult = Tuple[bool, str]
FileDescriptor = Dict[str, Union[bool, int, str]]
LinkDescriptor = FileDescriptor
FileList = List[FileDescriptor]
LinkList = List[LinkDescriptor]
DirDescriptor = Dict[str, Union[bool, int, FileList, LinkList]]
DirTree = Dict[str, DirDescriptor]

# Example for a DirTree
# {
#     "test/a": {
#         "files": [
#             {
#                 "name": "name.bla",
#                 "permission": 600,
#                 "rootuser": True,
#                 "rootgroup": True,
#                 "content": "b37b8487ac0b8f01e9e34949717b16d1"
#             }
#         ],
#         "links": [
#             {
#                 "name": "name.bla1",
#                 "target": "~/dotfiles/files/name1",
#                 "permission": 600,
#                 "rootuser": True,
#                 "rootgroup": True
#             },
#             {
#                 "name": "test.link",
#                 "target": "~/dotfiles/files/test",
#                 "permission": 777,
#                 "rootuser": False,
#                 "rootgroup": False
#             }
#         ],
#         "permission": 777,
#         "rootuser": True,
#         "rootgroup": True
#     },
#     "test/b": {...},
#     "test/b/c": {...},
# }
# Where the content property is optional for files


# Constants and helpers
###############################################################################

DIRNAME = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))
INSTALLED_FILE = os.path.join(DIRNAME, "../data/installed")
INSTALLED_FILE = os.path.join(INSTALLED_FILE, "regressiontests.json")
ENVIRONMENT = os.path.join(DIRNAME, "environment")
# Global used to store success of all tests
global_result = True


def cleanup() -> None:
    """Resets test environment and installed files"""
    for node in os.listdir(ENVIRONMENT):
        node = os.path.join(ENVIRONMENT, node)
        if os.path.isfile(node):
            os.remove(node)
        elif os.path.isdir(node):
            rmtree(node)
    if os.path.isfile(INSTALLED_FILE):
        os.remove(INSTALLED_FILE)


def init() -> None:
    """Initializes test environment and installed files"""
    os.chdir(DIRNAME)
    if not os.path.isdir(ENVIRONMENT):
        os.makedirs(ENVIRONMENT)
    cleanup()
    print("Starting regression tests...")
    print()
    print(79*"-")


# Test classes
###############################################################################

class RegressionTest():
    """This is the abstract base class for all regression tests.
    It provides simple start and check functionality"""
    def __init__(self, name: str, cmd_args: List[str], reset: bool):
        self.name = name
        self.cmd_args = ["python", os.path.abspath("../dotmgr.py"),
                         "--config", "test/test.ini",
                         "--save", "regressiontests",
                         "--quiet"] + cmd_args
        self.reset = reset

    def start(self) -> TestResult:
        """Starts the test and runs all checks"""
        if self.reset:
            cleanup()
        pre = self.pre_check()
        if not pre[0]:
            return {"success": False, "phase": "pre", "cause": pre[1]}
        process = Popen(self.cmd_args, stderr=PIPE, encoding="utf8")
        _, error_msg = process.communicate()
        exitcode = process.returncode
        if exitcode != 0:
            return {
                "success": False,
                "phase": "run",
                "cause": exitcode,
                "msg": error_msg
            }
        post = self.post_check()
        if not post[0]:
            return {"success": False, "phase": "post", "cause": post[1]}
        return {"success": True}

    @abstractmethod
    def pre_check(self) -> CheckResult:
        """The check executed before the test to make sure the test is
        run on the correct preconditions"""
        pass

    @abstractmethod
    def post_check(self) -> CheckResult:
        """The check executed after the test to make sure the test
        behave like expected"""
        pass

    def success(self) -> bool:
        """Execute this test. Expect it to be successful"""
        global global_result
        result = self.start()
        print(self.name + ": ", end="")
        if result["success"]:
            print('\033[92m' + "Ok" + '\033[0m')
        else:
            print('\033[91m\033[1m' + "FAILED" + '\033[0m'
                  + " in " + str(result["phase"]))
            print("Cause: " + str(result["cause"]))
            if "msg" in result:
                print("Error Message:")
                print(result["msg"])
        print(79*"-")
        global_result = global_result and result["success"]
        return result["success"]

    def fail(self, phase: str, cause: int) -> bool:
        """Execute this test. Expect a certain error"""
        global global_result
        result = self.start()
        print(self.name + ": ", end="")
        if not result["success"]:
            if result["cause"] != cause:
                print('\033[91m\033[1m' + "FAILED" + '\033[0m')
                print("Expected error: " + str(cause))
                print("Actual error: " + str(result["cause"]))
                if "msg" in result:
                    print("Error Message:")
                    print(result["msg"])
            else:
                print('\033[92m' + "Ok" + '\033[0m')
        else:
            print('\033[91m\033[1m' + "FAILED" + '\033[0m')
            print("Expected error in " + phase)
            print("Expected error: " + str(cause))
        print(79*"-")
        global_result = global_result and not result["success"]
        return not result["success"]


class DirRegressionTest(RegressionTest):
    """Regression check if Dotmanager makes the expected
    changes to the filesystem"""
    def __init__(self, name: str, cmd_args: List[str], before: DirTree,
                 after: DirTree, reset: bool):
        super().__init__(name, cmd_args, reset)
        self.before = before
        self.after = after

    @staticmethod
    def dircheck(dir_tree: DirTree) -> CheckResult:
        """Checks if dir_tree matches the actual directory
        tree in the filesystem"""

        def check_owner(path: str, props: Union[DirDescriptor,
                                                LinkDescriptor,
                                                FileDescriptor],
                        is_link: bool = False) -> None:
            """For owner permissions we only look up if its a normal
            user or the root user because we can't create other
            users just for the sake of these tests"""
            stat = os.lstat if is_link else os.stat
            if bool(stat(path).st_uid) == props["rootuser"]:
                user = "root" if props["rootuser"] else "user"
                raise ValueError((False, f"{path} is a not owned by {user}"))
            if bool(stat(path).st_gid) == props["rootgroup"]:
                group = "root" if props["rootgroup"] else "group"
                raise ValueError((False, f"{path} is a not owned by {group}"))

        def check_permission(path: str, permission: int) -> None:
            perm_real = str(oct(os.stat(path).st_mode))[-3:]
            if perm_real != str(permission):
                raise ValueError((False, f"{path} has permission {perm_real}"))

        for dir_name, dir_props in dir_tree.items():
            # Directory existance
            if not os.path.isdir(dir_name):
                raise ValueError((False, dir_name + " is a not a directory"))
            # Directory permission
            if "permission" in dir_props:
                check_permission(dir_name, dir_props["permission"])
            # Directory owner
            check_owner(dir_name, dir_props)
            # Files
            for file_props in dir_props["files"]:
                file_path = os.path.join(dir_name, file_props["name"])
                # File existance
                if os.path.islink(file_path) or not os.path.isfile(file_path):
                    raise ValueError((False, f"{file_path} is a not a file"))
                # File permission
                if "permission" in file_props:
                    check_permission(file_path, file_props["permission"])
                # File owner
                check_owner(file_path, file_props)
                # File content
                md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
                if "content" in file_props and md5 != file_props["content"]:
                    raise ValueError((False, f"{file_path} has wrong content"))
            # Links
            for link_props in dir_props["links"]:
                link_path = os.path.join(dir_name, link_props["name"])
                # Link existance
                if not os.path.islink(link_path):
                    raise ValueError((False, f"{link_path} is a not a link"))
                # Link permission
                if "permission" in link_props:
                    check_permission(link_path, link_props["permission"])
                # Link owner
                check_owner(link_path, link_props, True)
                # Link target
                target_path = os.path.abspath(os.readlink(link_path))
                link_props["target"] = os.path.abspath(link_props["target"])
                if target_path != link_props["target"]:
                    msg = f"{link_path} should point to {link_props['target']}"
                    msg += f", but points to {target_path}"
                    raise ValueError((False, msg))
                # Link target content
                md5 = hashlib.md5(open(target_path, "rb").read()).hexdigest()
                if "content" in link_props and md5 != link_props["content"]:
                    raise ValueError((False, f"{link_path} has wrong content"))

    def pre_check(self) -> CheckResult:
        try:
            self.dircheck(self.before)
        except ValueError as err:
            return err.args[0]
        return True, ""

    def post_check(self) -> CheckResult:
        try:
            self.dircheck(self.after)
        except ValueError as err:
            return err.args[0]
        return True, ""


# Test data
###############################################################################

before = {
    "environment": {
        "files": [],
        "links": [],
        "rootuser": False,
        "rootgroup": False
    }
}

after_nooptions = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name2",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name3",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_diroptions = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name5",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir": {
        "files": [],
        "links": [
            {
                "name": "name2",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir/subsubdir": {
        "files": [],
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir2": {
        "files": [],
        "links": [
            {
                "name": "name6",
                "target": "files/name6",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name7",
                "target": "files/name7",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_nameoptions = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir": {
        "files": [],
        "links": [
            {
                "name": "name",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name6",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir/subsubdir": {
        "files": [],
        "links": [
            {
                "name": "name",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_prefixsuffixoptions = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": ".name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name2bla",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name5",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir": {
        "files": [],
        "links": [
            {
                "name": "name3",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/name4": {
        "files": [],
        "links": [
            {
                "name": "test",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_links = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name2",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "name",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "filename4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False
            },
            {
                "name": "filename5",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir": {
        "files": [],
        "links": [
            {
                "name": "encrypt8",
                "target": "../data/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "rootuser": False,
                "rootgroup": False,
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "../data/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "rootuser": False,
                "rootgroup": False,
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_decrypt = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name_encrypt8",
                "target": "../data/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "rootuser": False,
                "rootgroup": False,
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt8",
                "target": "../data/decrypted/name_encrypt8#d6eb32081c822ed572b70567826d9d9d",
                "rootuser": False,
                "rootgroup": False,
                "content": "d6eb32081c822ed572b70567826d9d9d"
            },
            {
                "name": "encrypt9",
                "target": "../data/decrypted/name_encrypt9#e59ab101cf09636fc06d10bf3d56a5cc",
                "rootuser": False,
                "rootgroup": False,
                "content": "e59ab101cf09636fc06d10bf3d56a5cc"
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_merge = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "merge1",
                "target": "../data/merged/merge1#6ddb4095eb719e2a9f0a3f95677d24e0",
                "rootuser": False,
                "rootgroup": False,
                "content": "6ddb4095eb719e2a9f0a3f95677d24e0"
            },
            {
                "name": "merge3",
                "target": "../data/merged/merge2#04b6c550264c39e8b533d7f7b977415e",
                "rootuser": False,
                "rootgroup": False,
                "content": "04b6c550264c39e8b533d7f7b977415e"
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_pipe = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "file",
                "target": "../data/piped/file#fdb6e0c029299e6aabca0963120f0fa0",
                "rootuser": False,
                "rootgroup": False,
                "content": "fdb6e0c029299e6aabca0963120f0fa0"
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_nesteddynamic = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "merge1",
                "target": "../data/merged/merge1#526f328977744debf953a2c76c2c6169",
                "rootuser": False,
                "rootgroup": False,
                "content": "526f328977744debf953a2c76c2c6169"
            },
            {
                "name": "merge2",
                "target": "../data/piped/merge2#0281651775d0a19e648acf333cabac2f",
                "rootuser": False,
                "rootgroup": False,
                "content": "0281651775d0a19e648acf333cabac2f"
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_superprofile = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name2",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name3",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name5",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name6",
                "target": "files/name6",
                "rootuser": False,
                "rootgroup": False,
            }
        ],
        "rootuser": False,
        "rootgroup": False
    },
    "environment/subdir": {
        "files": [],
        "links": [
            {
                "name": "prefix_name2",
                "target": "files/name2",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "prefix_name3",
                "target": "files/name3",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "prefix_name4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "prefix_name5",
                "target": "files/name5",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "prefix_name6",
                "target": "files/name6",
                "rootuser": False,
                "rootgroup": False,
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_tags = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name1",
                "target": "files/name1",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name2",
                "target": "files/tag1%name2",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name5",
                "target": "files/tag3%name5",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name6",
                "target": "files/tag3%name6",
                "rootuser": False,
                "rootgroup": False,
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}

after_optional = {
    "environment": {
        "files": [],
        "links": [
            {
                "name": "name2",
                "target": "files/tag1%name2",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name3",
                "target": "files/tag2%name3",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name4",
                "target": "files/name4",
                "rootuser": False,
                "rootgroup": False,
            },
            {
                "name": "name10",
                "target": "files/tag%name10",
                "rootuser": False,
                "rootgroup": False,
            }
        ],
        "rootuser": False,
        "rootgroup": False
    }
}



# Test execution
###############################################################################

init()

DirRegressionTest("Simple",
                  ["-i", "NoOptions"],
                  before, after_nooptions, True).success()
DirRegressionTest("Option: name",
                  ["-i", "NameOption"],
                  before, after_nameoptions, True).success()
DirRegressionTest("Option: directory",
                  ["-i", "DirOption"],
                  before, after_diroptions, True).success()
DirRegressionTest("Option: prefix suffix",
                  ["-i", "PrefixSuffixOption"],
                  before, after_prefixsuffixoptions, True).success()
DirRegressionTest("Option: optional",
                  ["-i", "OptionalOption"],
                  before, after_optional, True).success()
DirRegressionTest("Command: links()",
                  ["-i", "Links"],
                  before, after_links, True).success()
DirRegressionTest("Command: decrypt()",
                  ["-i", "Decrypt"],
                  before, after_decrypt, True).success()
DirRegressionTest("Command: merge()",
                  ["-i", "Merge"],
                  before, after_merge, True).success()
DirRegressionTest("Command: pipe()",
                  ["-i", "Pipe"],
                  before, after_pipe, True).success()
DirRegressionTest("Command: Nested dynamicfiles",
                  ["-i", "NestedDynamicFile"],
                  before, after_nesteddynamic, True).success()
DirRegressionTest("Command: subprof()",
                  ["-i", "SuperProfile"],
                  before, after_superprofile, True).success()
DirRegressionTest("Command: tags()",
                  ["-i", "SuperProfileTags"],
                  before, after_tags, True).success()
DirRegressionTest("Conflict: Same profile linked twice",
                  ["-i", "SameProfileConflict"],
                  before, {}, True).fail("run", 102)
DirRegressionTest("Conflict: Same profile linked twice in subprofile",
                  ["-i", "SameProfileConflict2"],
                  before, {}, True).fail("run", 102)
DirRegressionTest("Conflict: Same link created twice",
                  ["-i", "SameLinkConflict"],
                  before, {}, True).fail("run", 102)
DirRegressionTest("Conflict: Link has multiple targets",
                  ["-i", "MultipleTargetsConflict"],
                  before, {}, True).fail("run", 102)

cleanup()
sys.exit(not global_result)



###############################################################################
# TODO: Write tests (only possible when regression tests use pygit2)
## option owner
## option replace and replace_pattern
## option permission
## extlink()
## env var substitution
## various conflicts
## blacklist
## .dotignore
