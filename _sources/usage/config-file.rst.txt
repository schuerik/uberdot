=============
Configuration
=============


Configuration files allow you to override defaults for commandline arguments, defaults for command options and even set
some settings that can't be set via commandline. The configuration file is an `INI-file`_ and can be created at the following locations:

    * **/etc/uberdot/uberdot.ini** for system-wide configuration
    * **/home/username/.config/uberdot/uberdot.ini** for only a specific user
    * **uberdot-repository/uberdot.ini** for portable installations

You can copy an example for the configuration file from ``docs/config-example.ini``.

Settings
--------

In this section are only settings which can't be set via commandline. Most of them have sane defaults, just make sure that ``profileFiles`` and
``targetFiles`` are set. Those are the only required settings. Example:

.. code:: ini

    [Settings]
    profileFiles    = /path/to/your/profiles/
    targetFiles     = /path/to/your/dotfiles/

The following settings are available:

+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| Name            | Values                                            | Description                                                      |
+=================+===================================================+==================================================================+
| askroot         | True, False (Default is True)                     | Shall uberdot ask for root permission if required                |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| backupExtension | String (Default is "bak")                         | The extension that is used to create backup files                |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| color           | True, False (Default is True)                     | Should the output be colorized                                   |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| decryptPwd      | String                                            | Default password to decrypt encrypted dotfiles                   |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| hashSeparator   | String (Default is "#")                           | The symbol that is used as separator for hashes in dynamic files |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| dataDir         | String (Default is None)                          | A setting to use a special directory instead of the default data |
|                 |                                                   | dir. Mainly useful for automated testing.                        |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| profileFiles    | Path (absolute or relatively to the installation) | The directory that contains the profiles                         |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| shell           | Path/Process name (Default is "bash")             | The shell that is used to execute shell scripts from event       |
|                 |                                                   | callbacks                                                        |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| shellTimeout    | Integer (Default is 60)                           | Time in seconds that a shell command is allowed to run           |
|                 |                                                   | without printing anything.                                       |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| smartShellCWD   | True, False (Default is True)                     | If true, event scripts will always start in the directory in     |
|                 |                                                   | which the profile started.                                       |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| tagSeparator    | String (Default is "%")                           | The symbol that is used as separator for tags in dotfile names   |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+
| targetFiles     | Path (absolute or relatively to the installation) | The directory that contains the dotfiles                         |
+-----------------+---------------------------------------------------+------------------------------------------------------------------+


Arguments
---------

The "Argument" section allows you to set defaults for commandline arguments.

+-----------------+---------------------------------------------------+-------------------------------------------------------+
| Name            | Values                                            | Description                                           |
+=================+===================================================+=======================================================+
| force           | True, False (Default is False)                    | Equivalent to --force                                 |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| dui             | True, False (Default is False)                    | Equivalent to --dui                                   |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| logginglevel    | info, verbose, quiet or silent (Default is info)  | Equivalent to --verbose, --quiet and --silent         |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| logfile         | Path                                              | Equivalent to --log                                   |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| makedirs        | True, False (Default is False)                    | Equivalent to --makedirs                              |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| skiproot        | True, False (Default is False)                    | Equivalent to --skiproot                              |
+-----------------+---------------------------------------------------+-------------------------------------------------------+
| superforce      | True, False (Default is False)                    | Equivalent to --superforce                            |
+-----------------+---------------------------------------------------+-------------------------------------------------------+


Defaults
--------

The "Default" section allows you to overwrite the default values of a profile. This includes defaults for command options,
the directory and the tags.

+-----------------+---------------------------------------------------+----------------------------------------------------------+
| Name            | Values                                            | Description                                              |
+=================+===================================================+==========================================================+
| directory       | Absolute or relative path to the repository       |  The directory a profile starts in                       |
|                 | (Default is "$HOME")                              |                                                          |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| name            | String (Default is "")                            | Sets default for the command option ``name``             |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| optional        | True, False (Default is False)                    | Sets default for the command option ``optional``         |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| owner           | String (Default is "")                            | Sets default for the command option ``owner``            |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| permission      | Integer (Default is 644)                          | Sets default for the command option ``permission``       |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| prefix          | String (Default is "")                            | Sets default for the command option ``prefix``           |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| replace         | String (Default is "")                            | Sets default for the command option ``replace``          |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| replace_pattern | String (Default is "")                            | Sets default for the command option ``replace_pattern``  |
+-----------------+---------------------------------------------------+----------------------------------------------------------+
| tags            | Comma-seperated list (Default is "")              | Sets default tags                                        |
+-----------------+---------------------------------------------------+----------------------------------------------------------+


Defaults for installed-files
----------------------------

You can overwrite your own defaults when you use multiple installed file.
For example if you create an installed file called "test" with ``--save test``, you could set the default starting directory to
your desktop like this:

.. code:: ini

    [Installed.test.Defaults]
    directory = /home/username/Desktop

This overwrites the section "Defaults" for all calls of uberdot that have ``--save test`` set.
You can do this for any section with the following naming schema: "Installed.<installed-file name>.<section name>"



.. _INI-file: https://en.wikipedia.org/wiki/INI_file
