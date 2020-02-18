#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def is_version_smaller(version_a, version_b):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_a)
    major_a, minor_a, patch_a = match.groups()
    major_a, minor_a, patch_a = int(major_a), int(minor_a), int(patch_a)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_b)
    major_b, minor_b, patch_b = match.groups()
    major_b, minor_b, patch_b = int(major_b), int(minor_b), int(patch_b)
    if major_a > major_b:
        return False
    if major_a < major_b:
        return True
    if minor_a > minor_b:
        return False
    if minor_a < minor_b:
        return True
    if patch_a > patch_b:
        return False
    if patch_a < patch_b:
        return True
    return False


def upgrade_stone_age(old_loaded):
    """Upgrade from old installed file with schema version 4 to fancy
    installed file. Luckily the schema only introduced optional properties,
    so we don't need to do anything.
    """
    return old_loaded

MIN_VERSION = "1.12.17_4"
upgrades = [
    ("1.16.0", upgrade_stone_age),
    # ("1.17.0", upgrade_owner)
]
