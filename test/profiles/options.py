"""This module collects all profiles that are used to test the options"""
from uberdot.profile import Profile

class NoOptions(Profile):
    def generate(self):
        link("name1", "name2", "name3")

class DirOption(Profile):
    def generate(self):
        link("name1")
        link("name2", directory="subdir")
        link("name3", directory="subdir/subsubdir")
        cd("subdir")
        link("name4", directory="subsubdir")
        link("name5", directory="..")
        links("name[67]", directory="../subdir2")

class NameOption(Profile):
    def generate(self):
        link("name1", name="name")
        link("name2", name="subdir/name")
        link("name3", directory="subdir", name="subsubdir/name")
        cd("subdir")
        link("name5", name="../name6", directory="subsubdir")

class PrefixSuffixOption(Profile):
    def generate(self):
        link("name1", prefix=".")
        link("name2", suffix="bla")
        link("name3", prefix="subdir/")
        link("name4", suffix="/test")
        link("name5")

class OptionalOption(Profile):
    def generate(self):
        tags("tag1", "tag2")
        links("name[2-4]")
        link("name10", optional=True)
        tags("tag")
        link("name10", optional=True)
