"""This module collects all profiles that are used to test updates of profiles.
"""
from uberdot.profile import EasyProfile

class DirOption(EasyProfile):
    def generate(self):
        link("name1", name="name11.file")
        link("name5")
        cd("subdir/subsubdir")
        link("name2", name="name3")
        link("name4", prefix="4")
