"""This module defines additional types used for type hints"""

###############################################################################
#
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
###############################################################################


from typing import Any
from typing import Dict
from typing import List
from typing import Union

# A strictly absolute path
Path = str
# A relative or absolute path
RelPath = str
# A string that will be interpreted as pattern
Pattern = str

# A (sub)set of options that can be set for any custom builtin
# For every option a default value is provided
Options = Dict[str, Any]

# Holds all information of a single link (to be) created
LinkDescriptor = Dict[str, Union[Path, str, bool, int]]

# Types for InstalledLog and its children
InstalledProfileLinkList = List[LinkDescriptor]
"""documented"""
InstalledProfileEntry = Union[str, InstalledProfileLinkList]
"""documented"""
InstalledProfile = Dict[str, InstalledProfileEntry]
"""documented"""
InstalledLogEntry = Union[str, InstalledProfile]
"""documented"""
# The InstalledLog is nothing more than an in-memory installed-file.
InstalledLog = Dict[str, InstalledLogEntry]
"""documented"""

# For generated profile results
ProfileLinkList = List[LinkDescriptor]
ProfileProfileList = List["ProfileResult"]
ProfileResultEntry = Union[str, "Profile", ProfileLinkList, ProfileProfileList]
# The ProfileResult is generated during profile execution. It contains all
# information and LinkDescriptors that describe the end result that is expected
# after the linking process is done.
ProfileResult = Dict[str, ProfileResultEntry]

# A DiffOperation contains information about a single atomic operation
# that is needed to fulfill what the ProfileResult prophesied.
# To do so, it needs to be interpreted by an interpreter
DiffOperation = Dict[str, Union[str, LinkDescriptor]]
# The DiffLogData is a list of all DiffOperations that will fulfill
# the ProfileResult if executed in order.
DiffLogData = List[DiffOperation]
