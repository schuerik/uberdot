"""This module collects all profiles that are used to test simple failures"""
from uberdot.profile import Profile

class NotAProfileFail:
    def generate(self):
        print("This should never be executed by uberdot")

class OverwriteBlacklisted(Profile):
    def generate(self):
        link("name1", name="untouched.file")

class RecursiveProfile(Profile):
    def generate(self):
        subprof("RecursiveProfile")

class CycleProfile1(Profile):
    def generate(self):
        subprof("CycleProfile2")

class CycleProfile2(Profile):
    def generate(self):
        subprof("CycleProfile1")
