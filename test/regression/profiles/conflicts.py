"""This module collects all profiles that are used to test conflicts"""
from uberdot.profile import EasyProfile

class SameProfileConflict(EasyProfile):
    def generate(self):
        subprof("Subprofile1")
        subprof("Subprofile1")

class SameProfileConflict2(EasyProfile):
    def generate(self):
        subprof("SubConflict1", "SubConflict2")

class SubConflict1(EasyProfile):
    def generate(self):
        subprof("Subprofile1")

class SubConflict2(EasyProfile):
    def generate(self):
        subprof("Subprofile1")

class SameLinkConflict(EasyProfile):
    def generate(self):
        link("name1")
        link("name1")

class MultipleTargetsConflict(EasyProfile):
    def generate(self):
        link("name1")
        link("name2", name="name1")

class NeedsRootConflict(EasyProfile):
    def generate(self):
        link("name1")
        link("name2", name="/etc/tmp_test")
