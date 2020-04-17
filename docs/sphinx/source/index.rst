=======
uberdot
=======

.. image:: https://travis-ci.com/schuerik/uberdot.svg?branch=master
    :target: https://travis-ci.com/schuerik/uberdot

.. image:: https://img.shields.io/github/tag/schuerik/uberdot?label=release
    :target: https://github.com/schuerik/uberdot/releases

.. image:: https://www.codefactor.io/repository/github/schuerik/uberdot/badge
    :target: https://www.codefactor.io/repository/github/schuerik/uberdot

.. image:: https://codecov.io/gh/schuerik/uberdot/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/schuerik/uberdot

.. image:: https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7%20%7C%203.8-blue.svg


uberdot is a tool to manage different versions of dotfiles/configs on different hosts. You can define small profiles
that specify which configuration files shall be symlinked.

Contents
--------

.. toctree::
   :maxdepth: 2

   usage/index.rst
   developers/index.rst


Why uberdot?
------------

Like probably most of the people that get into customizing/riceing linux, I started out with a few configuration files
for bash and some other tools. Soon I collected all of my configuration file in a repository and wrote a little script
that would create symlinks for me. But after some time my setup got more complex again and I ended up rewriting the script
several times. At this point I just wanted to have a more sophisticated program that could do everything that my script
could do. Indeed there are a ton of programs out there, that would do exactly this, but all of them seem to have forgotten
for whom those programs were made: People that want absolute control over their device. While it is nice to have a program
that does everything for you, needs (almost) no configuration and integrates into 3rd-party-software, those programs
take my beloved control. This is the key difference between uberdot and all other dotfile managers. uberdot is desinged
to give you maximal control, while trying to be as simple as possible and providing all features that other programs have.


Key feature
-----------

Like some of the more sophisticated dotfile managers uberdot will allow you to create profiles. Profiles define a set of
symbolic links that shall exist on your device. With other programs you would create a static json or yaml file in which
you basically hardcode which symblic links shall be created. Some programs support simple nesting of profiles, some
have feature like regular expression and some have more advanced features like templates to fight redundancies. The problem
I had with this approach was that after some time my setup eventually got more complex, so either I couldn't use the
dotfile manager anymore or I had to manually workaround the problem.
This is not the case with uberdot because profiles will be written in python. A very simple and small API will help you create
all the symlinks that you want. You can eliminate redundancies fully, nest profiles indefinitly, create blueprints
by utilizing inheritance, change the behaviour of profiles entirely and automate all workarounds directly within the profiles.
Furthermore there are a lot of settings and all defaults are customizable.


Other features
--------------

- Only a few to no tweaks needed to you dotfiles to start out
- Store your dotfiles wherever you like (simple directory, repository, cloud, usb drive, etc)
- Use multiple versions of a single dotfile
- Create links anywhere in the filesystem
- Create links that point anywhere in the filesystem (not exclusively to files in your repository)
- Set owner and permission for links
- Find and rename dotfiles using regular expressions
- Use encrypted dotfiles
- Split any dotfile in multiple parts where each part can have multiple versions
- You can simulate (dry run) everything to see if your self written profiles behave like you expect
- Advanced error handling and automatic integration tests on your self written profiles (even some semantic checks)
- Go back in time to a previous setup
- Logging
- Split files
- Events


You don't even need to know python or any programming language to use uberdot.

I created uberdot because none of the existing configuration/dotfile managers satisfied my needs. Either there were
essential features missing right away or after some time my setup got more complex and I ended up using the configuration
manager for only most of my dotfiles and had to manually work around some edge cases every god damn time. It also bothered me,
that with most dotfile managers you can't properly reuse profiles or (only parts of) configuration files.

uberdot aims to implement all features that all other configuration managers provide and is especially suited for complex
setups with multiple devices. Furthermore it allows to automate workarounds directly within the profiles and pushes reusability
of all your configuration files and profiles to it's limit.

uberdot is intended to give you maximal flexibility while checking the integrity of all operations that you
configured/programmed to prevent that you accidentally break your systems. To achieve this, profiles aren't static configuration
files but python classes to really give you all power you need.
If you don't know python don't worry, you won't need to know it to use uberdot, but if you do you can really go nuts with this.

Already working features:

- Very flexible generic python profiles
- Easy to use but powerful commands + clean syntax
- You can use your old repository without any changes. It doesn't matter how you organize your dotfiles.
- Use multiple versions of a single dotfile
- Advanced error handling (e.g. integration tests for your written profiles)
- Create links anywhere in the filesystem as you like ($HOME is not enough)
- Create links that point anywhere in the filesystem (not exclusively to your repository)
- Set owner and permission for links
- Find and rename dotfiles using regular expressions
- Use encrypted dotfiles
- Split any dotfile in multiple parts where each part can have multiple versions
- Provides an interface for system information (like hostname, distribution, etc)
- You can simulate (dry run) everything to see if your self written profiles behave like you expect

More features are coming:

- Templates
- Hard links (in some edge cases a symbolic link can't be used)
- Keep a history of all changes to go back in time
- Hooks
- Compability Layers for easy migration from other dotfile managers

About this documentation
------------------------

This documentation covers installation instructions, user guides, configuration examples
and guides for developers as well as a reference manual.

This documentation was generated for version |version| of uberdot.
