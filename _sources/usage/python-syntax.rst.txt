****************
Python explained
****************

Profiles are written in a programming language called python. This
document is intended to explain the syntax of python as easy as possible
for people that never ever heard of python. This is not an exhausted
explanation of python. It will only explain the few rules that you have
to follow to use uberdot.

Example
=======

.. code:: python

   from bin.profile import Profile

   class Main(Profile):
       def generate(self):
           tags("arch", "feh", "master")
           subprof("Git", "I3", "Bash", "Zsh", "Vim")

           #Misc
           link("tmux.conf")
           link("termite.conf", name=".config/termite/config")
           link("pacman.conf", directory="/etc")

A profile is a so called ``class`` in python. So every profile you want to
define will start with the keyword ``class`` followed by the name that you want
to call this profile. The following ``(Profile):`` is needed to tell python
that this class is actually a profile. Everything below this line that is
indented will belong to this profile. The correct indentation is very important
in python! The following line ``def generate(self):`` is not that important to
understand, but it does nothing more than defining a special function which
will be later executed by uberdot. Just put it always directly below the
line containing ``class``. Everything below this line needs to be indented
again. Now you can call the different commands that are explained in
:doc:`commands`. Important to know is that the parameters in the brackets need to be
surrounded by quotation marks and be separated by colons. The names like
``arch``, ``Git`` or ``tmux.conf`` need to be the first parameters. Options
like ``name=".config/termite/config"`` or ``directory="/etc"`` need to be
specified after those name parameters.

You can create multiple classes in one file. Just make sure that the
classes always start at the same indentation level.

The last thing to note is the first line of the example. Put this line
at the beginning of every file in that you create profiles.

If you still struggle with understanding how write a profile or how to
use certain commands take a look at the :doc:`example-configuration`.
