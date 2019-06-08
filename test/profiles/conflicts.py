"""This module collects all profiles that are used to test conflicts"""
from dotmanager.profile import Profile

class SameProfileConflict(Profile):
    def generate(self):
        subprof("Subprofile1")
        subprof("Subprofile1")

class SameProfileConflict2(Profile):
    def generate(self):
        subprof("SubConflict1", "SubConflict2")

class SubConflict1(Profile):
    def generate(self):
        subprof("Subprofile1")

class SubConflict2(Profile):
    def generate(self):
        subprof("Subprofile1")

class SameLinkConflict(Profile):
    def generate(self):
        link("name1")
        link("name1")

class MultipleTargetsConflict(Profile):
    def generate(self):
        link("name1")
        link("name2", name="name1")

class NeedsRootConflict(Profile):
    def generate(self):
        link("name1")
        link("name2", name="/etc/tmp_test")
