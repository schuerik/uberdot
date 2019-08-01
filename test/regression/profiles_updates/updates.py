"""This module collects all profiles that are used to test updates of profiles.
"""
from uberdot.profile import Profile

class DirOption(Profile):
    def generate(self):
        link("name1")
        link("name2", "name3", directory="subdir")
        link("name5", name="file")
