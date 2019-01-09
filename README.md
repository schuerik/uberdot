# Dotmanager

***This is currently under construction! Dotmanager is considered stable but not production ready at this point! Before I can
recommend using this there are a few things I want to have done:***
* ***Documentation***
* ***Unit and regression tests***
* ***Alpha test***

***Just come back in a few days, I'm constantly developing on this.***

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
- Alternate versions of dofiles
- Advanced error handling (eg integration tests of your written profiles)
- Create links anywhere in the filesystem as you like
- Create links that point anywhere in the filesystem (not exclusivley to your repository)
- Set owner and permission for links
- Find and rename dotfiles with regular expressions
- Use encrypted dotfiles
- Split a dotfile in multiple parts where each one can have alternate versions 
- Provides an interface for system information (like hostname, distribution, etc)
- You can simulate (dry run) everything to see if your self written profile behaves like you expect

More features are comming:
- Templates
- Copies (in some edge cases a link can't be used)
- Keep a history of all changes to go back in time
- Hooks

## Getting Started

### Installation
Clone this repository and install `python3.7`. If you want to use encrypted dotfiles you also need `gnupg`.
Switch into the cloned repository and copy the example config file `data/config-example.ini` to `data/dotmanger.ini`.
In this file you need to specify the properties `files` and `profiles` in the `Settings` section where `files` will be path of
the directory of your dotfiles (most likely a subdirectory in your repository) and `profiles` the directory in which you store
all the different profiles that you write (you should store them in a repository as well).

### Creating profiles
Create a file in your `profiles` directory. You can use any name as long as it ends with `.py`.
In this you can create a simple profile for example for your bash configuration:
``` python
from bin.profile import Profile
class Bash(Profile):
    def generate(self):
        link(".bashrc")
        link(".inputrc")
```
If you never used python before this might look confusing. Take a look at this
[short explanation](https://github.com/RickestRickSanchez/dotmanager/wiki/Python-syntax) that tells you everything you
need to understand whats going on here.
For everyone else its only important to know that a profile is just any python class that inherits of `Profile`. The name of the
subclass will be used as a universal identifier so make sure to name your profiles unique. The only thing you need to do is to
implement the `generate()` function.
This function can be thinked of as a shell script that starts in your home-directory. `link(".bashrc")` will search your
`files` directory for a file called `.bashrc` and creates a symlink in your home-directory that points to this file. There are
just a fistful of other commands like `cd()`, `subprof()` or `tags()` and some options that you can pass to them that will allow
you to create very flexible profiles with very easy but expressive syntax.

### Installing/Updating/Uninstalling profiles
Installing a profile called `Name`:
```
./dotmanager.py -i Name
```
If the profile is already installed, Dotmanager will search for changes between the already installed links and the profile and
will update those that changed.
Uninstalling an installed profile called `Name`:
```
./dotmanager.py -u Name
```
You can always use the `-d` flag to just simulate what will happen. This is especially useful if you changed your profiles, so
that you can be sure to don't mess up your system.
Take a look at [this full documentation](https://github.com/RickestRickSanchez/dotmanager/wiki/Commandline-interface) of all
commandline arguments.

## The commands
### cd(Path)
This command switches the directory like you are used to in UNIX. You can use relative paths, absolute paths and environment
variables or '~' in the path. All links that will be created after you switched the directory will be linked relative to this
directory.

### link(*Dotfilenames, **Options)
This command takes a list of dotfile names and creates a symlink for every single one of them in the current directory. It uses
the same name as the dotfile for the symlink as long you don't specify another one. This command lets you also set all options
defined in the section of the `opt()` command. But unlike the `opt()` command it also accepts an option called `directory` which
lets you switch the directory like `cd()`. This is handy if you have to link a few symlinks in different subdirectories of the
same parent directory.
This command also accepts dynamicfiles instead of filenames.

### opt(**Options)
There are several options that you can pass to functions like `link()` to control how links are set. The `opt()` command will
apply those options permanently for all functions that support setting options. This is a list of all options available:
- prefix: Every symlink name gets prepended with the provided prefix
    - eg `opt(prefix=".")`
- suffix: Same as prefix but appends to the symlink name
    - eg `opt(suffix=".ini")`
- owner: sets the user and group owner of the symlink
    - eg `opt(owner="peter:users")`
- permission: Sets the permission of the target file (symlinks are always 777)
    - eg `opt(permission=600)`
- preserve_tags: The tags of any dotfiles are stripped away for the symlink name. If you don't like this, set this to True.
    - eg `opt(preserve_tags=True)`
- replace_pattern: Specify a regular expression that will match what you want to replace in the filename
    - eg `opt(replace_pattern="vim(.+)")`
- replace: Specify a string that replaces the `replace_pattern`
    - eg `opt(replace="\1")` this will strip away any "vim" prefix of the symlinks name if used in combination with above example
- name: Sets the name of the symlink. This can be a path as well.
    - eg `opt(name="config")` but usually used like this `link("polybarconfig", name=".config/polybar/config")`
- optional: If no correct version of a file is found and this is set to True no error will be raised
    - eg `opt(optional=True)`

### default(*Optionnames)
This command accepts a list of options and sets them back to default. If no options is provided it sets all options back to
default.

### links(Pattern, **Options)
This command works like `link()` but instead of a list of filenames it recieves a regular expression. All dotfiles will be linked that matches this pattern (tags will be stripped away before matching). This can be very handy because you don't even have to edit your profile every time you add dotfile to your repository.
This command has also the advantage that you don't have to specify the `replace_pattern` property if you want to use `replace`. The search pattern will be reused if `replace_pattern` is not set.

### extlink(Path, **Options)
Creates a link to any file or directory by specifying a path. You can use a relative path if you want, but an absolute path is
considered safer in this case. Otherwise it behaves like the `link()` command.

### tags(*tags)
Takes a list of tags and adds all of them. A tag is just a any string of characters that you can set as you like. It will be
used to find alternate versions of a dotfile. Such a alternate version of a dotfile needs to be prefixed with the same tag plus
a percent sign as a separator. The easiest way to explain this concept is with an example.
Suppose you created a profile for your bash configuration:
``` python
from bin.profile import Profile
class Bash(Profile):
    def generate(self):
        link("bashrc", "inputrc", prefix=".")
```
This profile will search for the files `bashrc` and `inputrc` and links them to `.bashrc` and `.inputrc` in your home directory.
To reuse this profile on different distributions you can now create alternate versions of the files and name them like this:
- debian%bashrc
- debian%inputrc
- arch%bashrc
- arch%inputrc

Now you could create a profile for every device or distribution as you like and set the suitable tag.
``` python
from bin.profile import Profile
class Device1(Profile):
    def generate(self):
        tags("debian")
        subprof("Bash")
```
``` python
from bin.profile import Profile
class Device2(Profile):
    def generate(self):
        tags("arch")
        subprof("Bash")
```
So now just install Device1 on devices that are running Debian and Device2 on devices that are running Arch Linux. The idea is
that you create one "super" profile for every device and a profile for any program that you configure. By just setting the right
tags that describe the device and adding the subprofiles for the programs that you want to configure you can basically setup any
new device or variation of your configuration in a few minutes.

### rmtags(*tags)
Takes a list of tags. Removes all of them if they are set.

### has_tag(tags)
Takes a tag and returns if it is set.

### subprof(*profiles)
This command accepts a list of profilenames that will be executed as subprofiles. A subprofile takes all properties
(options, tags and the current working directory) of its parent at the time this command is called. It is considered good
practice to call this directly at the beginning of your profile but after the `tags()` because usually you don't want to use the
parents current working directory (which will most likely change) but want to start in your home directory.
A subprofile is connected with it's parent in that sense that it will be updated/removed when the parent is updated/removed.

### decrypt(Dotfilename)
This command takes a single filename and searches for it like `link()`. It will decrypt it and return the decrypted file as a
dynamicfile which then can be used by `link()`. If `decryptPwd` is set in your configfile this will be used for every
decryption. Otherwise Dotmanager (or more precisely gnupg) will ask you for the password. Because dynamicfiles have the
property to be regenerated every time the file contents changes, this command has the downside that it actually needs to decrypt
the file every time you install/update even though there maybe are no changes. This can be very frustrating if type in the
password every time so I strongly recommend setting `decryptPwd`.
**Example:**
This creates a DynamicFile called `gitconfig` at `data/decrypted`. The DynamicFile contains the decrypted content of the
encrypted dotfile `gitconfig`. Furthermore this creates a symlink to this DynamicFile in your home directory called
`.gitconfig`.
``` python
link(decrypt("gitconfig"), prefix=".")
```

### merge(name, *Dotfilenames)
This command lets you merge some dotfiles to a single big dotfile. That is useful if you want to split a configuration file that
doesn't support source-operations (eg i3). It even works with tags, so the dotfile can be generated using alternate versions of
the splittet files.
The first parameter is the name that you give the new merged dotfile. All following parameter are dotfiles that will be searched
for and merged in the order you provide. The command returns the merged dotfile as DynamicFile.
**Example:**
This creates a DynamicFile called `vimrc` at `data/merged/`. `vimrc` contains the content of the dotfiles `defaults.vim`,
`keybindings.vim` and `plugins.vim`. Furthermore this creates a symlink to this DynamicFile in your home directory called
`.vimrc`.
``` python
link(merge("vimrc", ["defaults.vim", "keybindings.vim", "plugins.vim"]), prefix=".")
```

## The info module
The info module provides a set of functions to get information about the system you are on.
At the moment the following functions are implemented:

| Function                    | Description                                                |
| --------------------------- | ---------------------------------------------------------- |
| `distribution()`            | Returns the distribution name (eg "Ubuntu", "Antergos")    |
| `hostname()`                | Returns the hostname                                       |
| `is_64bit()`                | Returns True if the OS is a 64 bit                         |
| `kernel()`                  | Returns the release of the running kernel (eg "4.19.4")    |
| `pkg_installed(pkg_name)`   | Returns True if the package called `pkg_name` is installed |
| `username()`                | Returns the name of the logged in user                     |

To use those functions you need to import the info module:
``` python
from bin import info
```
Then you can use it like this in a profile:
``` python
class Main(Profile):
    def generate(self):
        if info.pkg_installed("vim"):
            subprof("Vim")
            
        if info.distribution() == "Arch Linux":
            link("bash-pacman.sh", name=".bashrc")
        else:
            link("bash-apt-get.sh", name=".bashrc")
```

## FAQ
Please ask me whenever something is not obvious to you. I'm trying to make this as easy as possible.
