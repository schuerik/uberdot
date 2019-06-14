.. _getting-started:

===============
Getting started
===============


---------------------------------------------------------
Step 0: Put your dotfiles into version control (optional)
---------------------------------------------------------
I highly recommend to put all your dotfiles and the profiles that you are going
to write into a version control system like git or svn for obvious reasons. But
this is not required. The only requirement is that you have one directory that
contains all your dotfiles. Subdirectories are ok, just make sure that your
dotfiles are named uniquely.


--------------------
Step 1: Installation
--------------------
In near future there will be packages for AUR and pip available, as well as a
portable binary. But for now you will have to set up uberdot by yourself.

Step 1a: Manual set up
======================
First clone the repository:

.. code:: bash

    $ git clone https://github.com/schuerik/uberdot.git

Then install dependencies:

.. code:: bash

    $ sudo apt-get install python3
    # if you want to use encryption features
    $ sudo apt-get install python3 gnupg

You can run

.. code:: bash

    $ ./uberdot/test/regressiontest.py

to verify that uberdot runs correctly on your system.


---------------------
Step 2: Configuration
---------------------
There are a lot of things that you can configure in uberdot but for most of
them the defaults are enough. If you are interested in further configuration,
take a look at :doc:`config-file`. For the beginning you just have to set the
directory for your dotfiles and for your profiles. To do so, either create a new
file called ``uberdot.ini`` or copy the example from ``docs/config-example.ini``.

You can store the configuration file at one of the following places:
    - uberdot/data/uberdot.ini
    - ~/.config/uberdot/uberdot.ini
    - /etc/uberdot/uberdot.ini

Then set the values ``targetFiles`` and ``profileFiles`` in the "Settings" section:

.. code:: ini

    [Settings]
    profileFiles = /path/to/your/profiles/
    targetFiles  = /path/to/your/dotfiles/


-----------------------
Step 3: A first profile
-----------------------
For a simple test we will create a first profile. So go ahead and create a file
in your profile directory. It doesn't matter what you name it, as long it ends
on ".py".
You can copy the following, but replace ``<filename>`` with a file that exists in
your dotfile directory:

.. code:: python

    from uberdot.profile import profile

    class Test1(Profile):
        def generate():
            link("<filename>")

Now installing this profile is easy:

.. code:: bash

    $ ./udot.py -i Test1
    [Test1]: Installing new profile
    [Test1]: /home/user/<filename> was created and links to /path/to/your/dotfiles/<filename>
    Finished succesfully.

So ``link("<filename>")`` creates a symlink in your home directory and points
to the file ``<filename>`` in your repository.

Ok, lets modify this a little bit and add some more links:

.. code:: python

    from uberdot.profile import profile

    class Test1(Profile):
        def generate():
            link("<filename>", prefix=".")

            cd(".config")
            link("<filename2>")
            link("<filename3>", name="someothername.conf")

Of course ``link()`` isn't the only command that you can use. The ``cd()``
command let's you switch the directory in which the links will be created. So
instead of creating links in your home directory, all further calls of ``link()``
will create links in ``~/.config``.

.. code:: bash

    $ ./udot.py -i Test1
    [Test1]: Profile updated
    [Test1]: /home/user/<filename> was moved to /home/user/.<filename>
    [Test1]: /home/user/.config/<filename2> was created and links to /path/to/your/dotfiles/<filename2>
    [Test1]: /home/user/.config/someothername.conf was created and links to /path/to/your/dotfiles/<filename3>
    Finished succesfully.

As you can see, the profile gets updated now and only the difference to the
previous installed version of the profile is applied. Furthermore you can see
the effect of the options ``prefix`` and ``name`` that we passed to ``link()``.

---------------------
Step 4: Going further
---------------------

I want to show you two more commands, that provide key techniques of uberdot.
To make profiles more reusable you can use the ``subprof()`` command:


.. code:: python

    from uberdot.profile import profile

    class Vim(Profile):
        def generate():
            link("gvimrc", "vimrc", prefix=".")

            cd(".vim")
            link("keybindings.vim", "plugin.vim")
            link("python.snippets", "html.snippets", directory="UltiSnips")


    class Shell(Profile):
        def generate():
            link("zshrc", "bashrc", "inputrc", prefix=".")
            link("zsh_profile", name=".zprofile")

Here we have two profiles. The first one contains all configuration files for vim,
the second one for zsh and bash. You can embed them in any other profile as a
subprofile:

.. code:: python

    from uberdot.profile import profile

    class Test1(Profile):
        def generate():
            link("<filename>")

            subprof("Vim", "Shell")

Installing ``Test1`` again, results in the following output:

.. code:: bash

    $ ./udot.py -i Test1
    [Test1]: Profile updated
    [Test1]: /home/user/.<filename> was moved to /home/user/<filename>
    [Test1]: /home/user/.config/<filename2> was removed from the system.
    [Test1]: /home/user/.config/someothername.conf was removed from the system.
    [Vim]: Installing new profile as subprofile of Test1
    [Vim]: /home/user/.gvimrc was created and links to /path/to/your/dotfiles/gvimrc
    [Vim]: /home/user/.vimrc was created and links to /path/to/your/dotfiles/vimrc
    [Vim]: /home/user/.vim/keybindings.vim was created and links to /path/to/your/dotfiles/keybindings.vim
    [Vim]: /home/user/.vim/plugins.vim was created and links to /path/to/your/dotfiles/plugins.vim
    [Vim]: /home/user/.vim/UltiSnips/python.snippets was created and links to /path/to/your/dotfiles/python.snippets
    [Vim]: /home/user/.vim/UltiSnips/html.snippets was created and links to /path/to/your/dotfiles/html.snippets
    [Shell]: Installing new profile as subprofile of Test1
    [Shell]: /home/user/.zshrc was created and links to /path/to/your/dotfiles/zshrc
    [Shell]: /home/user/.bashrc was created and links to /path/to/your/dotfiles/bashrc
    [Shell]: /home/user/.inputrc was created and links to /path/to/your/dotfiles/inputrc
    [Shell]: /home/user/.zprofile was created and links to /path/to/your/dotfiles/zsh_profile
    Finished succesfully.

The subprofiles will be updated/removed, whenever you update/remove their
parent profile. This gets useful, when you have multiple devices of which
some use certain programs and some not (or shall not be configured), because
you can enable/disable whole sets of links.

This gets even more powerful in combination with the ``tags()`` command!
The problem with the above approach is that it is still very static.
Maybe you want Vim to use a shit load of plugins on
your work station, but use only a few plugins when running on a raspberry pi.
Thats were tagging comes into play.
You can add a tag to a file by prepending it to their filename, seperated by a
percent sign. When the tag is set, the file will be prefered over a untagged file.
We could create for example another dotfile called ``minimal%plugins.vim``,
where "minimal" is the tag and the percent sign is the seperator before the
original filename.
Our ``Test1`` profile will behave the same as before, but let's create a
new profile that will use the new minimal plugins file:

.. code:: python

    class Pi(Profile):
        def generate():
            tags("minimal")
            subprof("Vim", "Shell")

As you see can we set tags with the ``tags()`` command. When the tag is set, all
future commands will prefer the files that have "minimal" as tag in their filename.
If you set multiple tags they are prioritized in descending order. So the first
tag that you add will be prioritized over the second.

Let's take a look what happens if we install ``Pi``:

.. code::

    ERROR: Vim is already installed as subprofile of 'Test1'. You need to uninstall it first to avoid conflicts!

Oh, I totally forgot that I already have "Vim" installed as a subprofile of ``Test1``.
This would create an inconsistency because first a profile can't be installed twice at the
same time and second two profiles define contradicting configurations (one profile wants to
create a link to "plugins.vim" whereas the other profile wants to create the same link to
"minmal%plugins.vim").
uberdot detects such inconsistencies and tells you how to avoid them. I can now uninstall
just ``Vim``, but this would result in a similar error, because ``Shell`` is also subprofile
of ``Pi`` and ``Test1``. The better and most intuitive solution is to uninstall ``Test1``.
This removes the full configuration (and therefore also both subprofiles):

.. code:: bash

    $ ./udot.py -u Test1
    [Vim]: /home/user/.gvimrc was removed from the system.
    [Vim]: /home/user/.vimrc was removed from the system.
    [Vim]: /home/user/.vim/keybindings.vim was removed from the system.
    [Vim]: /home/user/.vim/plugins.vim was removed from the system.
    [Vim]: /home/user/.vim/UltiSnips/python.snippets was removed from the system.
    [Vim]: /home/user/.vim/UltiSnips/html.snippets was removed from the system.
    [Vim]: Uninstalled Profile
    [Shell]: /home/user/.zshrc was removed from the system.
    [Shell]: /home/user/.bashrc was removed from the system.
    [Shell]: /home/user/.inputrc was removed from the system.
    [Shell]: /home/user/.zprofile was removed from the system.
    [Shell]: Uninstalled profile
    [Test1]: /home/user/<filename> was removed from the system.
    [Test1]: Uninstalled Profile
    Finished succesfully.

Now we can finally install ``Pi``:

.. code:: bash

    $ ./udot.py -i Pi
    [Pi]: Installing new Profile
    [Vim]: Installing new profile as subprofile of Pi
    [Vim]: /home/user/.gvimrc was created and links to /path/to/your/dotfiles/gvimrc
    [Vim]: /home/user/.vimrc was created and links to /path/to/your/dotfiles/vimrc
    [Vim]: /home/user/.vim/keybindings.vim was created and links to /path/to/your/dotfiles/keybindings.vim
    [Vim]: /home/user/.vim/plugins.vim was created and links to /path/to/your/dotfiles/minimal%plugins.vim
    [Vim]: /home/user/.vim/UltiSnips/python.snippets was created and links to /path/to/your/dotfiles/python.snippets
    [Vim]: /home/user/.vim/UltiSnips/html.snippets was created and links to /path/to/your/dotfiles/html.snippets
    [Shell]: Installing new profile as subprofile of Pi
    [Shell]: /home/user/.zshrc was created and links to /path/to/your/dotfiles/zshrc
    [Shell]: /home/user/.bashrc was created and links to /path/to/your/dotfiles/bashrc
    [Shell]: /home/user/.inputrc was created and links to /path/to/your/dotfiles/inputrc
    [Shell]: /home/user/.zprofile was created and links to /path/to/your/dotfiles/zsh_profile
    Finished succesfully.

You can see that the subprofiles behave the same as for ``Test1``, but
``/home/user/.vim/plugins.vim`` points now to
``/path/to/your/dotfiles/minimal%plugins.vim``. The idea is that
you create profiles for all kind of programs that you want to configure
and create configuration files with different tags that describe properties of the
system they are for, so that in the end you can quickly create a new profile
for a new device, by just picking the programs that are installed and telling
uberdot what tags will be applied for the device.

Of course that is just one way to work with tags and just one way to alternate
versions of a dotfile.

For further configuration you should take a look at the other
`commands and options <https://schuerik.github.io/uberdot/usage/commands.html>`_.
You probably won't need all of them, but they can solve a lot of
common problems and will shorten your profiles. The documentation also covers a
lot of topics that will help you understanding what is going on under the hud, as
well as more advanced examples and troubleshooting.
