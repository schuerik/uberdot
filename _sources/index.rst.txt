==========
Dotmanager
==========

.. image:: https://travis-ci.com/RickestRickSanchez/dotmanager.svg?branch=master
    :target: https://travis-ci.com/RickestRickSanchez/dotmanager

.. image:: https://img.shields.io/github/release/RickestRickSanchez/dotmanager.svg
    :target: https://github.com/RickestRickSanchez/dotmanager/releases/latest

.. image:: https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager/badge
    :target: https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager

.. image:: https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7-blue.svg


Dotmanager is a tool to manage different versions of dotfiles/configs on different hosts. You can define little profiles
that specify which configuration files shall be symlinked.

Contents
--------

.. toctree::
   :maxdepth: 2

   usage/index.rst
   developers/index.rst


Why Dotmanager?
---------------

I created Dotmanager because none of the existing configuration/dotfile managers satisfied my needs. Either there were
essential features missing right away or after some time my setup got more complex and I ended up using the configuration
manager for only most of my dotfiles and had to manually work around some edge cases every god damn time. It also bothered me,
that with most dotfile managers you can't properly reuse profiles or (only parts of) configuration files.

Dotmanager aims to implement all features that all other configuration managers provide and is especially suited for complex
setups with multiple devices. Furthermore it allows to automate workarounds directly within the profiles and to easily reuse all
your configuration files and profiles.

Dotmanager is intended to give you maximal flexibility while checking the integrity of all operations that you
configured/programmed to prevent that you accidentally break your systems. To achieve this, profiles aren't static configuration
files but python classes to really give you all power you need.
If you don't know python don't worry, you won't need to know it to use Dotmanger, but if you do you can really go nuts with this.


About this documentation
------------------------

This documentation covers installation instructions, user guides, configuration examples
and guides for developers as well as a reference manual.

This documentation was generated for version |version| of Dotmanager.
