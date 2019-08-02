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

class PrefixSuffixExtensionOption(Profile):
    def generate(self):
        link("name1", prefix=".")
        link("name2", suffix="bla")
        link("name5", "name11.file", extension="png")
        link("name6")
        # Prefix and suffix should usually not be used like this but this is
        # the expected behaviour
        link("name3", prefix="subdir/")
        link("name4", suffix="/test")

class OptionalOption(Profile):
    def generate(self):
        tags("tag1", "tag2")
        links("name[2-4]")
        extlink("doesnotexist", optional=True)
        link("name10", optional=True)
        tags("tag")
        link("name10", optional=True)

class ReplaceOption(Profile):
    def generate(self):
        link("name2", "name3", replace_pattern="name", replace="file")
        tags("tag1")
        cd("subdir")
        link("name2", "name3", replace_pattern="name", replace="file")

class OptionArgument(Profile):
    def generate(self):
        link("name1")
        default("prefix")
        link("name2")
        rmtags("tag1")
        link("name6", name="file2")
