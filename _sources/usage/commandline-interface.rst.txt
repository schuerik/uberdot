*********************
Commandline Interface
*********************


Synopsis
========

::

 udot.py MODE [OPTIONS...] [PROFILES...]


Modes
=====

One - and only one - of the following modes has to be chosen:


-h, --help
    Shows a short help message with all options and modes and exits

--version
    Displays the version of uberdot and exits

-i, --install
    Installs every specified profile. If a profile is already installed
    it will be updated instead of installed.

-u, --uninstall
    Uninstalls every specified profile. If a profile is not installed,
    uberdot will skip this profile.

-s, --show
    Shows information about installed profiles and links. If you specify
    ``PROFILES`` this will show only information about those profiles.
    Otherwise information about all installed profiles will be shown.


Options
=======


--config <CONFIG>
     Use a different config file for this call


--directory <DIRECTORY>
     Overwrite the default directory temporarily


-d, --dry-run
     Just simulate the changes uberdot would perform


--dui
     Use an alternative startegy to install profiles and links. The default
     strategy will do this by recursively going through the profiles and
     create/update/remove all links one by one. This can cause conflicts if
     e.g. a link is moved from one to another profile. This strategy installs
     links by first doing all removals, then all updates and at last all new
     installs. Most conflicts should be solved by this strategy but it has the
     downside that the output isn’t that clear as the normal strategy.


-f, --force
     Allows overwrites of files that already exists in your filesystem


--log <LOGFILE>
     Log everything into a logfile (this also adds timestamps to the log messages)


-m, --makedirs
     Make directories if they don’t exist. Any directory that will be created
     inherits the owner of its parent directory.


--option <KEY=VAL...>
     Sets/Overwrites one or more keys of the option section of the config file.


--parent <PARENT>
     Forces the profiles that you install/update to be installed as subprofile
     of ``PARENT``. This should be only needed to solve certain conflicts.


--print
     Prints the ``Difference Log`` unformatted and exits. Only useful for
     debugging.


-p, --pretty-print
     Prints out the changes that uberdot would perform if executed without
     this flag. This differs from ``--dry-run`` in that way that it won’t do
     any checks on the profiles or filesystem, so ``--dry-run`` is almost
     always to prefer. The only use-case is if your profiles will raise an
     error and aborts but you want to now what would have happen to get a
     better understanding of the issue in your profile/workflow itself.


-q, --quiet
     Print no log messages but warnings and errors.


--save <SAVE>
     Use another ``installed-file`` for this execution. Can be used to install
     profiles multiple times on the same device. This is potentially dangerous
     because conflict detection works only within a single ``installed-file``.
     You need to make sure by yourself that there are no conflicts between all
     installed profiles and the profiles that you are going to install.
     This is mostly useful if you want to test the linking process in another
     directory or if those profiles are installed in completely different
     locations on your device but you don't want your current setup be changed.


--silent
     Print no log messages at all.


--skiproot
    Skip all operations that would require root permission


--superforce
     Overwrites files and links that are blacklisted because it is considered
     dangerous to overwrite those files e.g. ``/etc/hosts`` or ``/etc/passwd``


-v, --verbose
     Print more information of the linking process and a stacktrace when an
     error occurs.



Profiles
========

This is a space seperated list of profiles. Any profile will be identified by
its class name, not by its filename. Don’t forget that python class names are
case-sensitive.


Examples
========

1. Uninstall the profile called "Main" and all its subprofiles

.. code:: bash

    $ ./udot.py -u Main

2. Install the profiles "Main" and "Main2" and all their subprofiles

.. code:: bash

    $ ./udot.py -i Main Main2

3. Just simulate previous installation

.. code:: bash

    $ ./udot.py -id Main Main2

4. Perform the same installation like before but set the prefix for all links to "."

.. code:: bash

    $ ./udot.py -i --option prefix=. -- Main Main2

5. Also set the tags "debian" and "big"

.. code:: bash

    $ ./udot.py -i --option prefix=. tags=debian,big -- Main Main2

6. Install "Main" and all it's subprofiles, make non-existing directories and
   overwrite existing files

.. code:: bash

    $ ./udot.py -imf Main
