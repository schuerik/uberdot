# Dotmanager

***This is currently under construction! I don't have much time at the moment but I'm constantly developing on this.***
***If you want to try out Dotmanager, go ahead, it is stable and working. But be aware that there are a lot of changes coming that will break compatibility.***


[![Build Status](https://travis-ci.com/RickestRickSanchez/dotmanager.svg?branch=master)](https://travis-ci.com/RickestRickSanchez/dotmanager)
[![Latest Release](https://img.shields.io/github/release/RickestRickSanchez/dotmanager.svg)](https://github.com/RickestRickSanchez/dotmanager/releases/latest)
[![Python version](https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7-blue.svg)]()
[![Regressiontest coverage](https://codecov.io/gh/RickestRickSanchez/dotmanager/branch/master/graph/badge.svg)](https://codecov.io/gh/RickestRickSanchez/dotmanager)
[![CodeFactor](https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager/badge)](https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager)

## What is Dotmanager?
Dotmanager is a tool to manage different versions of dotfiles/configs on different hosts. You can define little profiles
that specify which configuration files shall be symlinked.

I created Dotmanager because none of the existing configuration/dotfile managers satisfied my needs. Either there were
essential features missing right away or after some time my setup got more complex and I ended up using the configuration
manager for only most of my dotfiles and had to manually work around some edge cases every god damn time. It also bothered me,
that with most dotfile managers you can't properly reuse profiles or (only parts of) configuration files.

Dotmanager aims to implement all features that all other configuration managers provide and is especially suited for complex
setups with multiple devices. Furthermore it allows to automate workarounds directly within the profiles and pushes reusability
of all your configuration files and profiles to it's limit.

Dotmanager is intended to give you maximal flexibility while checking the integrity of all operations that you
configured/programmed to prevent that you accidentally break your systems. To achieve this, profiles aren't static configuration
files but python classes to really give you all power you need.
If you don't know python don't worry, you won't need to know it to use Dotmanger, but if you do you can really go nuts with this.

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


## Installation Instructions / Documentation / Wiki / Examples
Information about how to install and use Dotmanager, as well as some tutorials and examples can be found in the [documentation](https://rickestricksanchez.github.io/dotmanager/).
