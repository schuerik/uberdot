# Dotmanager

***This is currently under construction! Dotmanager is considered stable but not production ready at this point! Before I can
recommend using this there are a few things I want to have done:***
* ***Documentation***
* ***Unit and regression tests***
* ***Alpha test***

***Just come back in a few days, I'm constantly developing on this.***


[![Build Status](https://travis-ci.com/RickestRickSanchez/dotmanager.svg?branch=master)](https://travis-ci.com/RickestRickSanchez/dotmanager)
## What is Dotmanager?
Dotmanager is a tool to manage different versions of your dotfiles on different hosts. Dotmanager is intended to give you
maximal flexibility while checking all operations you configured/programmed at the same time to prevent that you accidentally
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
- You can simulate (dry run) everything to see if your self written profile behaves like you expect

More features are coming:
- Templates
- Hard links (in some edge cases a symbolic link can't be used)
- Keep a history of all changes to go back in time
- Hooks


## Getting Started

### Installation
Clone this repository and install `python3.7`. If you want to use encrypted dotfiles you also need `gnupg`.
Switch into the cloned repository and copy the example config file `docs/config-example.ini` to `data/dotmanger.ini`.
In this file you need to specify the properties `files` and `profiles` in the `Settings` section where `files` will be path of
the directory of your dotfiles (most likely a subdirectory in your repository) and `profiles` the directory in which you store
all the different profiles that you write (you should store them in a repository as well).

### Creating profiles
Create a file in your `profiles` directory. You can use any name as long as it ends with `.py`.
In this you can create a simple profile for example for your bash configuration:
``` python
from dotmanager.profile import Profile
class Bash(Profile):
    def generate(self):
        link(".bashrc")
        link(".inputrc")
```
If you never used python before this might look confusing. Take a look at this
[short explanation](docs/documentation/python-syntax.md) that tells you everything you need to understand whats going on here.
For everyone else its only important to know that a profile is just any python class that inherits of `Profile`. The name of the
subclass will be used as a universal identifier so make sure to name your profiles unique. The only thing you need to do is to
implement the `generate()` function.
This function can be thunk of as a shell script that starts in your home-directory. `link(".bashrc")` will search your
`files` directory for a file called `.bashrc` and creates a symlink in your home-directory that points to this file. There are
just a fistful of other commands like `cd()`, `subprof()` or `tags()` and some options that you can pass to them that will allow
you to create very flexible profiles with very easy but expressive syntax.

### Installing/Updating/Uninstalling profiles
Installing a profile called `Name`:
```
./dotmgr.py -i Name
```
If the profile is already installed, Dotmanager will search for changes between the already installed links and the profile and
will update those that changed.
Uninstalling an installed profile called `Name`:
```
./dotmgr.py -u Name
```
You can always use the `-d` flag to just simulate what will happen. This is especially useful if you changed your profiles, so
that you can be sure to don't mess up your system.
Take a look at [this full documentation](docs/documentation/commandline-interface.md) of all commandline arguments.


## Documentation / Wiki / Examples
For more information about how to use Dotmanager please take a look at the [documentation](docs/documentation/contents.md).


## FAQ
Please ask me whenever something is not obvious to you. I'm trying to make this as easy as possible.
