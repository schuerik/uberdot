"""This module collects all profiles that are used to test updates of profiles.
"""
from uberdot.profile import Profile

class DirOption(Profile):
    def generate(self):
        link("name1")
        link("name2", "name3", directory="subdir")
        link("name5", name="file")

class SuperProfileTags(Profile):
    def generate(self):
        subprof("Subprofile3")
        tags("tag1", "tag2")
        link("name1")
        subprof("Subprofile1")

class Subprofile3(Profile):
    def generate(self):
        link("name5")
        link("name2")

class Subprofile1(Profile):
    def generate(self):
        links("name[34]")
        link("name6")
