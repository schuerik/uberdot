# Dotmanager

***This is currently under construction! I don't have much time at the moment but I'm constantly developing on this.***
***If you want to try out Dotmanager, go ahead, it is stable and working. But be aware that there are a lot of changes coming that will break compatibility.***


[![Build Status](https://travis-ci.com/RickestRickSanchez/dotmanager.svg?branch=master)](https://travis-ci.com/RickestRickSanchez/dotmanager)
[![Latest Release](https://img.shields.io/github/release/RickestRickSanchez/dotmanager.svg)](https://github.com/RickestRickSanchez/dotmanager/releases/latest)
[![Python version](https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7-blue.svg)]()
[![CodeFactor](https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager/badge)](https://www.codefactor.io/repository/github/rickestricksanchez/dotmanager)

## What is Dotmanager?
Dotmanager is a tool to manage different versions of your dotfiles on different hosts. Dotmanager is intended to give you
maximal flexibility while checking the integrity of all operations that you configured/programmed to prevent that you accidentally
break your systems. To achieve this you can write simple profiles which will define a set of dotfiles that you want to install.
Unlike any other dotfile tool which lets you create profiles, those aren't static configuration files but python classes to
really give you all flexibility and power you need. If you don't know python don't worry, you won't need to know it to use
Dotmanger, but if you do you can really go nuts with this.

Features:
- Very flexible generic python profiles
- Easy to use but powerful commands + clean syntax
- You can use your old repository without any changes. It doesn't matter how you organize your dotfiles.
- Alternate versions of dotfiles
- Advanced error handling (eg. integration tests for your written profiles)
- Create links anywhere in the filesystem as you like
- Create links that point anywhere in the filesystem (not exclusively to your repository)
- Set owner and permission for links
- Find and rename dotfiles using regular expressions
- Use encrypted dotfiles
- Split a dotfile in multiple parts where each one can have alternate versions
- Provides an interface for system information (like hostname, distribution, etc)
- You can simulate (dry run) everything to see if your self written profiles behave like you expect

More features are coming:
- Templates
- Hard links (in some edge cases a symbolic link can't be used)
- Keep a history of all changes to go back in time
- Hooks


## Installation Instructions / Documentation / Wiki / Examples
Information about how to install and use Dotmanager, as well as some tutorials and examples can be found in the [documentation](https://rickestricksanchez.github.io/dotmanager/).
