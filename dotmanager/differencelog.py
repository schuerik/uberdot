""" This module implements the Difference-Log """

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
#
###############################################################################


from typing import Optional
from typing import List
from dotmanager.interpreters import Interpreter
from dotmanager.types import LinkDescriptor
from dotmanager.types import DiffLogData
from dotmanager.types import Path
from dotmanager.utils import get_date_time_now


class DiffLog():
    """This class holds the DiffLogData and provides helpers to
    create and insert DiffLogOperations. Furthermore it provides
    run_interpreter() that allows to run several interpreter
    at the same time"""
    def __init__(self, data: Optional[DiffLogData] = None) -> None:
        if data is None:
            self.data = []
        else:
            self.data = data

    def add_info(self, profilename: str, message: str) -> None:
        """Print an info for the user"""
        self.__append_data("info", profilename, message=message)

    def add_profile(self, profilename: str, parentname: str = None) -> None:
        """Create an empty profile in the installed file"""
        self.__append_data("add_p", profilename, parent=parentname)

    def update_profile(self, profilename: str) -> None:
        """Update the changed-date of a profile"""
        self.__append_data("update_p", profilename)

    def update_parent(self, profilename: str, parentname: str) -> None:
        """Update the changed-date and parent of a profile"""
        self.__append_data("update_p", profilename, parent=parentname)

    def remove_profile(self, profilename: str) -> None:
        """Remove an empty profile from the installed file"""
        self.__append_data("remove_p", profilename)

    def add_link(self, symlink: LinkDescriptor, profilename: str) -> None:
        """Add this symlink to a given profile"""
        symlink["date"] = get_date_time_now()
        self.__append_data("add_l", profilename, symlink=symlink)

    def remove_link(self, symlink_name: Path,
                    profilename: str) -> None:
        """Remove this symlink to a given profile"""
        self.__append_data("remove_l", profilename, symlink_name=symlink_name)

    def update_link(self, installed_symlink: LinkDescriptor,
                    new_symlink: LinkDescriptor, profilename: str) -> None:
        """Update installed symlink1 to symlink2"""
        new_symlink["date"] = get_date_time_now()
        self.__append_data("update_l", profilename,
                           symlink1=installed_symlink,
                           symlink2=new_symlink)

    def __append_data(self, operation: str, profilename: str, **args) -> None:
        """Put new item into data"""
        self.data.append(
            {"operation": operation, "profile": profilename, **args}
        )

    def run_interpreter(self, *interpreters: List[Interpreter]) -> None:
        """Run a list of interpreters for all DiffOperations in DiffLogData"""
        # Initialize interpreters
        for interpreter in interpreters:
            interpreter.set_difflog_data(self.data)
        # Send a "start" operation to indicate that operations will follow
        # so interpreters can implement _op_start
        for interpreter in interpreters:
            interpreter.call_operation({"operation": "start"})
        # Run interpreters for every operation
        for operation in self.data:
            for interpreter in interpreters:
                interpreter.call_operation(operation)
        # And send a "fin" operation when we are finished
        for interpreter in interpreters:
            interpreter.call_operation({"operation": "fin"})
