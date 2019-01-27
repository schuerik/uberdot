"""This module collects all profiles that are used to test commands"""
from dotmanager.profile import Profile

class Links(Profile):
    def generate(self):
        links("name1")
        links("\w{4}2")
        links("\w{2}(.{2})3", replace=r"na\1")
        links("\w{4}([45])", replace=r"filenam\1", replace_pattern=".*(.\d)")
        cd("subdir")
        links("name_(encrypt[89])", replace=r"\1", encrypted=True)

class Decrypt(Profile):
    def generate(self):
        link(decrypt("name_encrypt8"))
        link(decrypt("name_encrypt8"), replace_pattern="name_(encrypt8)", replace=r"\1")
        link(decrypt("name_encrypt9"), name="encrypt9")

class Merge(Profile):
    def generate(self):
        link(merge("merge1", ["name1", "name2"]))
        link(merge("merge2", ["name3", "name4", "name5"]), name="merge3")

class NestedDynamicFile(Profile):
    def generate(self):
        link(merge("merge1", [decrypt("name_encrypt8"), "name2"]))

class SuperProfile(Profile):
    def generate(self):
        link("name1")
        subprof("Subprofile1", "Subprofile2")
        opt(prefix="prefix_")
        cd("subdir")
        subprof("Subprofile3", "Subprofile4")

class SuperProfileTags(Profile):
    def generate(self):
        tags("tag1", "tag2")
        link("name1")
        subprof("Subprofile1")
        tags("tag3")
        rmtags("tag1")
        subprof("Subprofile2")

class Subprofile1(Profile):
    def generate(self):
        links("name[2-4]")

class Subprofile3(Profile):
    def generate(self):
        links("name[2-4]")

class Subprofile2(Profile):
    def generate(self):
        links("name[56]")

class Subprofile4(Profile):
    def generate(self):
        links("name[56]")
