"""This module defines additional types used for type hints"""

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
InstalledProfileEntry = Union[str, InstalledProfileLinkList]
InstalledProfile = Dict[str, InstalledProfileEntry]
InstalledLogEntry = Union[str, InstalledProfile]
# The InstalledLog is nothing more than an in-memory installed-file.
InstalledLog = Dict[str, InstalledLogEntry]

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
