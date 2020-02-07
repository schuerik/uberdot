"""This module handles writing and loading installed-files. """

###############################################################################
#
# Copyright 2018 Erik Schulz
#
# This file is part of uberdot.
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
###############################################################################


import os
import json
from uberdot import constants as const
from uberdot.errors import FatalError
from uberdot.errors import PreconditionError
from uberdot.errors import UnkownError
from uberdot.utils import has_root_priveleges
from uberdot.utils import get_uid
from uberdot.utils import get_gid
from uberdot.utils import log_debug


class InstalledFile(dict):
    def __init__(self):
        try:
            self.loaded = json.load(open(const.installed_file))
        except FileNotFoundError:
            log_debug("No installed file found.")

    # TODO: Support more than one version
    # TODO: Return only profiles for the current user
    # TODO: Secure writing/deleting, so try-blocks and backups wont be needed
    # TODO: Support relative paths and environment vars
    # TODO: Support timeline


        # Check installed-file version
        # self.version_check_high(self.loaded["@version"])
        # self.version_check_low(self.loaded["@version"])

    # def version_check_high(self, compare_version):
        # if compare_version > constants.MAX_SCHEMA_VERSION:
        #     msg = "uberdot is too old to process the installed-files."
        #     msg += "Only a schema up to version "
        #     msg += str(constants.MAX_SCHEMA_VERSION) + " is"
        #     msg += " supported, but one installed file is already using"
        #     msg += "version " + str(compare_version) + "."
        #     raise PreconditionError(msg)

    # def version_check_low(self, compare_version):
        # if compare_version < constants.MIN_SCHEMA_VERSION:
        #     msg = "The installed-file is too old to be processed by uberdot."
        #     msg += "The schema version needs to be at least "
        #     msg += str(constants.MIN_SCHEMA_VERSION) + "."
        #     raise PreconditionError(msg)


    # def __setitem__(self, key, value):
        # curr_dict = self.sys_dict if self.use_sys else self.user_dict
        # curr_dict[key] = value

    # def __delitem__(self, key):
        # curr_dict = self.sys_dict if self.use_sys else self.user_dict
        # curr_dict.__delitem__(key)

    # def keys(self):
        # return set(self.user_dict.keys()).union(self.sys_dict.keys())

    # def has_key(self, key):
        # return key in self.keys()

    # def __getitem__(self, key):
