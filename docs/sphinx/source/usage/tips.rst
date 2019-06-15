****
Tips
****

Set decryption password
=======================

If you use encrypted dotfiles you should really set the password in your
``uberdot.ini`` config. Otherwise you will have to type it in
literally everytime that you execute uberdot because uberdot will
never know if the file changed until it decrypted it.


Create aliases for uberdot
=============================

You should create aliases for uberdot in your favourite shell so you
can access it from everywhere. For example:

.. code:: bash

   alias dot = ~/repos/uberdot/udot.py
   alias dup = ~/repos/uberdot/udot.py -i  # Update profiles
   alias drm = ~/repos/uberdot/udot.py -u  # Remove profiles
   alias dls = ~/repos/uberdot/udot.py -s  # List installed profiles


Organizing profiles
===================

Personally I prefer to divide my profiles in profiles for devices and
for programs. So your directory tree for profiles could look like this:

::

   profiles
   ├── devices
   │   ├── laptop.py
   │   ├── pi.py
   │   ├── desktop.py
   │   └── work.py
   ├── main.py
   └── programs
       ├── bash.py
       ├── git.py
       ├── i3.py
       ├── polybar.py
       ├── rofi.py
       ├── vim.py
       └── zsh.py

In this example I have also a ``main.py`` module at the top level that I
use as super class. Every device that should use my main setup would
inherit of a profile called “Main”. Of course you can put all profiles
in a single module but I like it to be a bit more separated.
