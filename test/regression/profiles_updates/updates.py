"""This module collects all profiles that are used to test updates of profiles.
"""
from uberdot.profile import Profile

class DirOption(Profile):
    def generate(self):
        link("name1", permission=755)
        link("name2", "name3", directory="subdir")
        link("name5", name="file")
        link("file", name="name11.file")

class SuperProfileTags(Profile):
    def generate(self):
        subprof("Subprofile3")
        tags("tag1", "tag2")
        link("name1", permission=600)
        subprof("Subprofile1")

class Subprofile3(Profile):
    def generate(self):
        link("name5")
        link("name2")

class Subprofile1(Profile):
    def generate(self):
        links("name[34]")
        link("name6")

class SuperProfileEvent(Profile):
    prepare_script = """
        alias s='echo "Hello" >> '
        function t(){
            echo "$2" >> $1
        }
        echo -e "\\u2192"
    """
    beforeInstall = """
        t test.file "I come first"
    """
    def generate(self):
        link("name1")
        subprof("SubprofileEvent")

class SubprofileEvent(Profile):
    beforeInstall = """
        # Just a comment
        s test.file
    """
    beforeUpdate = "t test.file update"
    beforeUninstall = "rm test.file"
    afterInstall = "cp name2 name4"
    afterUpdate = "t test.file $(cat name4)"
    afterUninstall = """
        if [[ -e name2 ]]; then
            exit 1;
        else
            rm name4;
        fi
    """
    def generate(self):
        links("name[234]")
