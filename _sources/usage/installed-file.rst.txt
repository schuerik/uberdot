***************
Installed files
***************

The installed files store what links were created by Dotmanger. This
document explains how it is structured and how you can fix those file if
a critical unexpected error occurs.


Structure
=========

Installed files are JSON files that are stored in ``data/installed/``.
If you use the ``--save`` flag you can set the name of the installed
file that Dotmanger should use otherwise ``default.json`` is used.

This is a example of such a installed file.

.. code:: javascript

   {
       "@version": "1.5.0_3",
       "Main": {
           "name": "Main",
           "links": [
               {
                   "target": "/home/user/repos/dotfiles/files/tmux.conf",
                   "name": "/home/user/tmux.conf",
                   "uid": 1000,
                   "gid": 100,
                   "permission": 644,
                   "date": "2018-11-28 11:06:14"
               },
               {
                   "target": "/home/user/repos/dotfiles/files/termite.conf",
                   "name": "/home/user/.config/termite/config",
                   "uid": 1000,
                   "gid": 100,
                   "permission": 644,
                   "date": "2018-11-28 11:06:14"
               },
               {
                   "target": "/home/user/repos/dotfiles/files/antergos%pacman.conf",
                   "name": "/etc/pacman.conf",
                   "uid": 0,
                   "gid": 0,
                   "permission": 644,
                   "date": "2019-01-02 09:03:33"
               }
           ],
           "installed": "2018-11-28 11:06:14",
           "updated": "2019-01-02 09:03:33"
       },
       "Git": {
           "name": "Git",
           "links": [
               {
                   "target": "/home/user/repos/dotfiles/files/work%gitconfig",
                   "name": "/home/user/.gitconfig",
                   "uid": 1000,
                   "gid": 100,
                   "permission": 644,
                   "date": "2018-11-28 11:06:14"
               },
               {
                   "target": "/home/user/repos/dotfiles/files/gitconfig_system",
                   "name": "/etc/gitconfig",
                   "uid": 0,
                   "gid": 0,
                   "permission": 644,
                   "date": "2018-11-28 11:06:14"
               }
           ],
           "installed": "2018-11-28 11:06:14",
           "updated": "2018-11-28 11:06:14",
           "parent": "Main"
       }
   }

As you can see it stores a JSON Object with a ``@version`` key and a key
for every installed profile. Generally keys that start with “@” are
reserved special keys (but at the moment only the version key exists)
and all other keys are the names of installed profiles.

@version key
------------

The version key is important because Dotmanager will compare it to its
own version and will refuse to read the installed file if the installed
file schema version (the number after the underscore) does not match its
own installed file schema version.

Profile keys
------------

For every profile that is installed there exists a key. It stores a
dictionary with the following keys:

- name: The name of the profile
- parent: If the profile is a subprofile this key contains the name
  of the parent (super) profile, otherwise the key doesn’t exist
- installed: The date of the first installation
- updated: The date of the last modification
- links: Contains a list of all installed links by this profile

links key
~~~~~~~~~

The links key in a profile contains a list of all installed links. For
each link there is a dictionary storing the following information:

- target: The absolut path to to the dotfile in your repo
- name: The absolute path of the symlink
- uid: The userid of the link owner
- gid: The groupid of the link owner
- permission: The permission of the target
- date: The date of the last modification


Installed file is corrupted
===========================

This should actually never happen and if it does please create a bug
ticket so we can make sure that this won’t happen again. But it is
possible -in very early versions of Dotmanager this happened a lot- that
an unexpected error occurs during the linking process. For those cases
Dotmanager creates a backup of the installed file before modifying it.
You will need to look into the backup and the modified version and
verify if all removals/additions/updates were really written to the
filesystem. When you are certain that the current installed file matches
the state of your filesystem you can remove the backup file and use
dotmanager again.

Version update
==============

Dotmanager refuses to read the installed file if the installed file
schema version does not match it’s own version. This can happen when you
update Dotmanager and have an old installed file left on your device. To
circumvent this issue you have two opportunities:

1. Revert to an old version of Dotmanager, uninstall all profiles,
   update Dotmanager, install all uninstalled profiles again
2. Look into the changes of the installed file, update the installed file
   manually, increment the version number
