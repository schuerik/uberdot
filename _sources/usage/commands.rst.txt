Commands
========

A profile provides several so called “commands” that you will use to create
links, set options, decrypt dotfiles and much more. They are called commands
because they behave similar to shell script commands and they won’t need to be
prepended with ``self`` like every other class function needs to in python.
This document explains all those commands and gives examples on how to use
them. The commands are devided into "Basic Commands", "Helper Commands" and
"File manipulation commands".



Basic commands
--------------


cd(Path)
^^^^^^^^

This command switches the directory like you are used to in UNIX. You
can use relative paths or absolute paths and make use of environment
variables or ‘~’ in the path. All links that will be created after you
switched the directory will be linked relative to this directory.

**Example:**

.. code:: python

   # Switch to home directory
   cd("~")
   cd("$HOME")
   # Switch to a subdirectory called "config"
   cd("config")
   # Using absolute paths
   cd("/home/user")


link(\*Dotfilenames, directory="", \*\*Options)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This command takes a list of dotfile names and creates a symlink for
every single one of them in the current directory. It uses the same
name as the dotfile for the symlink as long you don’t specify another
one. This command lets you also set all options defined in the section
of the ``opt()`` command. But unlike the ``opt()`` command it also
accepts another option called ``directory`` which lets you switch the
directory like ``cd()``. This is handy if you have to link a few
symlinks in different subdirectories of the same parent directory.
This command also accepts dynamicfiles instead of filenames.

**Example:**

.. code:: python

   # Find tmux.conf and create a link in the current directory
   link("tmux.conf")
   # Find pacman.conf and create a link in /etc
   link("pacman.conf", directory="/etc")
   # Find zsh_profile and create a link called .zprofile in the current directory
   link("zsh_profile", name=".zprofile")
   # Find polybarconfig and polybarlaunch.sh and create two links named according to the replace regex:
   # polybarconfig -> config
   # polybarlaunch.sh -> launch.sh
   link("polybarconfig", "polybarlaunch.sh", replace_pattern="polybar(.+)", replace=r"\1")
   # Find hosts and mkinitcpio.conf and create links in /etc
   cd("/etc")
   link("hosts", "mkinitcpio.conf")
   # In combination with a dynamicfile (in this case using decrypt())
   link(decrypt("id_rsa"), dircetory=".ssh")


opt(\*\*Options)
^^^^^^^^^^^^^^^^

There are several options that you can pass to functions like
``link()`` to control how links are set. The ``opt()`` command will
apply those options permanently for all functions that support setting
options. This is a list of all options available:

.. role:: python(code)
   :language: python

- **prefix**: Every symlink name gets prepended with the provided prefix

  - e.g.: :python:`opt(prefix=".")`

- **suffix**: Same as prefix but appends to the symlink name. Note that
  if the symlink name has an extension, the suffix will be inserted before
  the extension.

  - e.g.: :python:`opt(suffix="somestring")`

- **extension**: Add or replace the extension of the symlink name

  - e.g.: :python:`opt(extension="ini")`

- **owner**: Sets the user and group owner of the symlink

  - e.g.: :python:`opt(owner="peter:users")`

- **permission**: Sets the permission of the target file (symlinks are
  always 777)

  - e.g.: :python:`opt(permission=600)`

- **replace_pattern**: Specify a regular expression that will match what
  you want to replace in the filename

  - e.g.: :python:`opt(replace_pattern="vim(.+)")`

- **replace**: Specify a string that replaces the ``replace_pattern``

  - e.g.: :python:`opt(replace=r"\1")` this will strip away any “vim”
    prefix of the symlinks name if used in combination with above
    example

- **name**: Sets the name of the symlink. This can be a path as well.

  - e.g.: :python:`opt(name="config")` but usually used like this
    :python:`link("polybarconfig", name=".config/polybar/config")`

- **optional**: If no correct version of a file is found and this is set
  to True no error will be raised

  - e.g.: :python:`opt(optional=True)`

- **secure**: If set to True the symlink target will be chown to match the
  owner of the symlink. Otherwise the target will be chown to the user that
  started uberdot. Defaults to True.

  - e.g.: :python:`opt(secure=False)`


links(Pattern, encrypted=False, directory="", \*\*Options)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This command works like ``link()`` but instead of a list of filenames
it receives a regular expression. All dotfiles will be linked that
match this pattern (tags will be stripped away before matching). This
can be very handy because you don’t even have to edit your profile
when you add a new dotfile to your repository as long you use the same
naming pattern for those files. This command also has the advantage
that you don’t have to specify the ``replace_pattern`` property if you
want to use ``replace``. The search pattern will be reused for this
purpose if ``replace_pattern`` is not set. Another feature unique to
this command is that it supports the option ``encrypted`` which will
decrypt every file that matches link, when set to True.

**Example:**

.. code:: python

   # Find the files gvimrc and vimrc and create the links called .gvimrc and .vimrc
   links("g?vimrc", prefix=".")
   # Find all files that match "rofi-*.rasi" and create links that strip away the "rofi-"
   links("rofi-.+\.rasi", replace_pattern="rofi-(.+\.rasi)", replace=r"\1")
   links("rofi-(.+\.rasi)", replace=r"\1")  # Does the same as above
   # Decrypt files on the fly
   links("wifi-(.+).gpg", replace=r"\1", encrypted=True)


extlink(Path, directory="", \*\*Options)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a link to any file or directory by specifying a path. Relative
paths will be relatively to the directory the pofile is currently in.
The links name will be the same as the file or the directory if you don't
set another. Otherwise it behaves like the ``link()`` command.

**Example:**

.. code:: python

   # Create a symlink from ~/.wallpapers/wallpaper.png to ~/owncloud/data/pictures/wallpaper.png
   extlink("owncloud/data/pictures/wallpaper.png", directory=".wallpapers")
   # Create a symlink from ~/Pictures to ~/owncloud/data/Camera/
   extlink("~/owncloud/data/Camera", name="Pictures")


tags(\*tags)
^^^^^^^^^^^^

Takes a list of tags and adds all of them. A tag is just any string of
characters (except for ‘%’) that you can choose as you like. It will be
used to find alternate versions of a dotfile. Such a alternate version
of a dotfile needs to be prefixed with the same tag plus a percent
sign as a separator. The easiest way to explain this concept is with
an example. Suppose you created a profile for your bash configuration:

.. code:: python

   from uberdot.profile import Profile
   class Bash(Profile):
       def generate(self):
           link("bashrc", "inputrc", prefix=".")

This profile will search for the files ``bashrc`` and ``inputrc`` and
links them to ``.bashrc`` and ``.inputrc`` in your home directory. To
reuse this profile on different distributions you can now create
alternate versions of the files and name them like this:

- debian%bashrc
- debian%inputrc
- arch%bashrc
- arch%inputrc

Now you could create a profile for every device or distribution as you
like and set the suitable tag.

.. code:: python

   from uberdot.profile import Profile
   class Device1(Profile):
       def generate(self):
           tags("debian")
           subprof("Bash")

.. code:: python

   from uberdot.profile import Profile
   class Device2(Profile):
       def generate(self):
           tags("arch")
           subprof("Bash")

So just install Device1 on devices that are running Debian and Device2
on devices that are running Arch Linux. The idea is that you create one
“super” profile for every device and a profile for any program that you
configure. By just setting the right tags that describe the device and
adding the subprofiles for the programs that you want to configure you
can basically setup any new device or variation of your configuration in
a few minutes.


subprof(\*profiles)
^^^^^^^^^^^^^^^^^^^

This command accepts a list of profilenames that will be executed as
subprofiles. A subprofile takes all properties (options, tags and the
current working directory) of its parent at the time this command is
called. It is considered good practice to call this directly at the
beginning of your profile but after the ``tags()`` because usually you
don’t want to use the parents current working directory (which will
most likely change) but want to start in your home directory. A
subprofile is connected with it’s parent in that sense that it will be
updated/removed when the parent is updated/removed.

**Example**: This will search for the profiles ``Bash``, ``Vim`` and
``I3`` and install them as subprofile of ``Main``. If no default
directory was set ``Main`` starts in your home-directory. This means
``Bash`` and ``Vim`` would also start in your home-directory, whereas
``I3`` would start at ``~/.config/``.

.. code:: python

   class Main(Profile):
       def generate(self):
           subprof("Bash", "Vim")
           cd(".config")
           subprof("I3")



Helper commands
---------------


find(Dotfilename)
^^^^^^^^^^^^^^^^^

Search for a dotfile like ``link()`` or other commands do. It returns the absolute
path to the dotfile. If no matching file is found, ``None`` will be returned.
If more than one file is found, an error will be raised.
You can overwrite this function to change the searching behaviour of the entire
profile.


has_tag(tags)
^^^^^^^^^^^^^

Takes a tag and returns if it is set.


rmtags(\*tags)
^^^^^^^^^^^^^^

Takes a list of tags. Removes all of them if they are set.


default(\*Optionnames)
^^^^^^^^^^^^^^^^^^^^^^

This command accepts a list of options and sets them back to default.
If no option is provided it sets all options back to default. Tags are
handeled internally as an option that has list of tags, so you can
reset them with ``default()`` as well.

**Example:**

.. code:: python

   # Set one option back to default
   default("permission")
   # Set multiple option back to default
   default("optional", "owner", "prefix")
   # Set all option (tags inclusive) back to default
   default()
   # Remove all tags (the default list of tags is empty)
   default("tags")



File manipulation commands
--------------------------


decrypt(Dotfilename)
^^^^^^^^^^^^^^^^^^^^

This command takes a single filename and searches for it like ``link()``. It
will decrypt it and return the decrypted file as a dynamicfile which then can
be used by ``link()``. If ``decryptPwd`` is set in your configfile this will be
used for every decryption. Otherwise uberdot (or more precisely gnupg) will
ask you for the password. Because all dynamicfiles are regenerated every time a
profile gets executed, this command has the downside that it actually asks for
the decryption password even though nothing changed, so I highly recommend setting
``decryptPwd``.

**Example:** This creates a DynamicFile called ``gitconfig`` at
``data/decrypted``. The DynamicFile contains the decrypted content of the
encrypted dotfile ``gitconfig``. Furthermore this creates a symlink in your
home directory called ``.gitconfig`` which points to the DynamicFile.

.. code:: python

   link(decrypt("gitconfig"), prefix=".")

**Example:** To decrypt multiple files at once you could use python’s list
comprehension or use ``links()`` with ``encrypted`` setting. This will decrypt
``key1``, ``key2``, ``key3`` and ``key4`` and link them to ``key1.pkk``,
``key2.pkk``, ``key3.pkk`` and ``key4.pkk``.

.. code:: python

   # using list comprehension
   keyfiles = [decrypt(file) for file in ["key1", "key2", "key3", "key4"]]
   link(keyfiles, suffix=".pkk")
   # instead of decrypting every file by itself
   link(decrypt("key1"), decrypt("key2"), decrypt("key3"), decrypt("key4"), suffix=".pkk")
   # or use the links() command with encrypted option
   links("key[1-4]", suffix=".pkk", encrypted=True)


merge(name, \*Dotfilenames)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This command lets you merge multiple dotfiles into a one big dotfile. That
is useful if you want to split a configuration file that doesn’t support
source-operations (e.g. i3). It even works with tags, so the dotfile can be
generated using alternate versions of the splittet files. The first parameter
is the name that you give the new merged dotfile. All following parameters are
dotfiles that will be searched for and merged in the order you provide. The
command returns the merged dotfile as DynamicFile.

**Example:** This creates a DynamicFile called ``vimrc`` at ``data/merged/``.
``vimrc`` contains the content of the dotfiles ``defaults.vim``,
``keybindings.vim`` and ``plugins.vim``. Furthermore this creates a symlink to
this DynamicFile in your home directory called ``.vimrc``.

.. code:: python

   link(merge("vimrc", ["defaults.vim", "keybindings.vim", "plugins.vim"]), prefix=".")


pipe(Dotfilename, shell_command)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This command lets you execute any shell command on a dotfile before
linking it by piping its content into the specified shell command. It returns the
result as a DynamicFile. This command also accepts a Dynamicfile instead
of a filename.

**Example:** Think of a file ``text.txt`` that only contains the numbers
one to twenty with each number on a separate line.

.. code:: python

   link(pipe("test.txt", "grep 2"))

This will create a link called ``test.txt`` which only contains the numbers 2,
12 and 20.
