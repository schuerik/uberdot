"""This module collects all profiles that are used to test updates of profiles.
"""
from uberdot.profile import EasyProfile

class DirOption(EasyProfile):
    def generate(self):
        link("name1", permission=755)
        link("name2", "name3", directory="subdir")
        link("name5", name="file")
        link("file", name="name11.file")

class SuperProfileTags(EasyProfile):
    def generate(self):
        subprof("Subprofile3")
        tags("tag1", "tag2")
        link("name1", permission=600)
        subprof("Subprofile1")

class Subprofile3(EasyProfile):
    def generate(self):
        link("name5")
        link("name2")

class Subprofile1(EasyProfile):
    def generate(self):
        links("name[34]")
        link("name6")

class Subprofile2(EasyProfile):
    def generate(self):
        links("name[56]")

class Subprofile5(EasyProfile):
    def generate(self):
        link("name11.file")

class DynamicFiles(EasyProfile):
    def generate(self):
        link(decrypt("name_encrypt8"), name="name_encrypt6")
        link(decrypt("name_encrypt9"), name="name_encrypt7")
        link(merge("merge1", ["name1", "name2"]), name="merge3")
        link(merge("merge2", ["name1", "name2"]), name="merge4")

class SuperProfileEvent(EasyProfile):
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

class SubprofileEvent(EasyProfile):
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
