Info module
===========

The info module provides a set of functions to get information about the
system you are on.

Functions
---------

**info.distribution()**

    Returns the distribution name (e.g. “Ubuntu”, “Antergos”)

**info.hostname()**

    Returns the hostname

**info.is_64bit()**

    Returns ``True`` if the OS is a 64 bit

**info.kernel()**

    Returns the release of the running kernel (e.g. “4.19.4”)

**info.pkg_installed(pkg_name)**

    Returns ``True`` if the package called ``pkg_name`` is installed

**info.username()**

    Returns the name of the logged in user


Usage
-----

To use those functions you need to import the info module:

.. code:: python

   from uberdot import info

Then you can use it like this in a profile:

.. code:: python

   class Main(Profile):
       def generate(self):
           # Install the profile "Vim" if the package vim is installed
           if info.pkg_installed("vim"):
               subprof("Vim")

           # Link a .bashrc with aliases for pacman instead of apt-get if Arch Linux is installed
           if info.distribution() == "Arch Linux":
               link("bash-pacman.sh", name=".bashrc")
           else:
               link("bash-apt-get.sh", name=".bashrc")
