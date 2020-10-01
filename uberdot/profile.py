"""This module implements the superclass for all profiles and contains globals
and the ``@commands``-Decorator.

|
"""

###############################################################################
#
# Copyright 2020 Erik Schulz
#
# This file is part of uberdot.
#
# uberdot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# uberdot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with uberdot.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################


import builtins
import os
import re
import shutil
from abc import abstractmethod
from copy import deepcopy
from uberdot.dynamicfile import *
from uberdot.state import GenLinkData, GenProfileData
from uberdot.utils import *

const = Const()

original_builtins = list(builtins.__dict__.keys())
"""A list of the builtins before they were modified in any way"""



class LoaderEntry:
    def __init__(self, name, class_obj, params={}):
        self.name = name
        self.class_obj = class_obj
        self.params = params


class ProfileLoader(metaclass=Singleton):
    def __init__(self):
        self.file_mapping = []
        self.extension_mapping = [
            ("py", ProfileLoader.import_profiles_by_classname),
            ("yaml", ProfileLoader.parse_yaml_easy_profile),
            ("json", ProfileLoader.parse_static_json_profile)
        ]
        self._loaded_profiles = {}
        # Run preload.py if available
        preload_path = os.path.join(const.settings.profile_files, "preload.py")
        if os.path.exists(preload_path):
            log_debug("Executing '" + preload_path + "'.")
            preload_mod = ProfileLoader.import_module(preload_path)
            if hasattr(preload_mod, "conf_file_mapping"):
                self.file_mapping = preload_mod.conf_file_mapping + self.file_mapping
            if hasattr(preload_mod, "conf_extension_mapping"):
                self.extension_mapping = preload_mod.conf_extension_mapping + self.extension_mapping
        self.load_profiles()

    @staticmethod
    def import_module(file, supress=False):
        if not os.path.exists(file):
            msg = "'" + file + "' can't be imported because it does not exist."
            raise PreconditionError(msg)
        try:
            # TODO: errors in modules seem not to raise exceptions
            spec = importlib.util.spec_from_file_location("__name__", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as err:
            if not supress:
                raise err

    @staticmethod
    def parse_static_json_profile(file):
        parsed = json.load(file)
        entry = LoaderEntry(parsed["name"], StaticParsedProfile, parsed)
        result[parsed["name"]] = entry
        return result

    @staticmethod
    def parse_yaml_easy_profile(file):
        parsed = yaml.load(file)
        entry = LoaderEntry(parsed["name"], EasyParsedProfile, parsed)
        result[parsed["name"]] = entry
        return result

    @staticmethod
    def import_profiles_by_classname(file):
        try:
            module = ProfileLoader.import_module(file)
        except CustomError as err:
            raise err
        except Exception as err:
            msg = "The module '" + file + "' contains an error and therefor "
            msg += "can't be imported. The error was:\n   " + str(err)
            raise PreconditionError(msg)
        result = {}
        for class_name, class_obj in vars(module).items():
            if isinstance(class_obj, type) and issubclass(class_obj, ProfileSkeleton):
                result[class_name] = LoaderEntry(class_name, class_obj)
        return result

    def extend_mappings(self, extra_files=None, extra_ext=None):
        if extra_files:
            self.file_mapping = extra_files + self.file_mapping
        if extra_ext:
            self.extension_mapping = extra_ext + self.extension_mapping

    def load_profiles(self):
        log_debug("Loading profiles from '" + const.settings.profile_files + "'.")
        self._loaded_profiles.clear()
        for filename in walk_profiles():
            if os.path.basename(filename) == "preload.py":
                continue
            load_entries = self.__parse_profilefile(filename)
            if load_entries is not None:
                self._loaded_profiles.update(load_entries)
        log_debug("Found: " + ", ".join(self.available_profiles()))

    def available_profiles(self):
        return list(sorted(self._loaded_profiles.keys()))

    def __parse_profilefile(self, filename):
        # First go through all file path mappings
        for relpath, func in self.file_mapping:
            abs_path = os.path.join(const.settings.profile_dir, relpath)
            # When abs_path is a directory the file has to be in any subdir
            if os.path.isdir(abs_path):
                if filename.startswith(abs_path):
                    loader_func = func
                    break
            # Otherwise the filename has to match exactly
            else:
                if filename == abs_path:
                    loader_func = func
                    break
        # When we couldn't find a matching mapping via filenames
        # we go through all the extension mappings
        else:
            for ext, func in self.extension_mapping:
                if os.path.splitext(filename)[1][1:] == ext:
                    loader_func = func
                    break
            else:
                msg = "No loading mechanism for file '"
                msg += filename + "' available."
                log_warning(msg)
                return
        # Generate all LoadEntries for each profile in file
        load_entries = loader_func(filename)
        # Check that all returned profiles inherit from ProfileSkeleton
        for name, entry in load_entries.items():
            if not issubclass(entry.class_obj, ProfileSkeleton):
                msg = "Profile '" + name + "' cant be loaded as it is"
                msg += " not a subclass of ProfileSkeleton."
                raise PreconditionError(msg)
        return load_entries

    def get_class(self, name):
        try:
            return self._loaded_profiles[name].class_obj
        except KeyError:
            raise PreconditionError("Can't get class for profile '" + name + "'.")

    def new_object(self, name, data={}, params={}):
        try:
            load_entry = self._loaded_profiles[name]
        except KeyError:
            msg = "Can't create object for profile '" + name + "'. No such profile."
            raise PreconditionError(msg)
        params = {**load_entry.params, **params}
        return load_entry.class_obj.new(name, data, params)


# Abstract class that implements the absolute minimum of profiles
class ProfileSkeleton:
    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.result = GenProfileData(name=self.name)

    @classmethod
    def new(cls, name, data, params):
        return cls(name, data, **params)

    @abstractmethod
    def start_generation(self):
        """This is the wrapper for :func:`generate()`. It can be used for
        setting up and tearing down the generation and will be called from
        an UberDot instance or another profile. :func:`generate()` must not
        be called without this wrapper.

        Returns:
            dict: The result dictionary :attr:`self.result<Profile.result>`
        """
        raise NotImplementedError

    @abstractmethod
    def generate(self):
        raise NotImplementedError


# Base class for most profiles.
class BaseProfile(ProfileSkeleton):
    def __init__(self, name, data):
        super().__init__(name, data)
        self.parent = self.data.get("parent", None)
        if self.check_cycle():
            self._gen_err("Detected a cycle in your subprofiles!")
        self.result["parent"] = None if self.parent is None else self.parent.name
        self.executed = False
        self.child_data = None

    def start_generation(self):
        """This is the wrapper for :func:`generate()`. It provides
        mechanisms for setting up and tearing down the generation,
        logging and error handling.

        .. warning:: Do NOT call this within the same profile, only
            from outside!!

        Returns:
            dict: The result dictionary :attr:`self.result<Profile.result>`
        """
        if self.executed:
            self._gen_err("A profile can be only generated " +
                          "one time to prevent side-effects!")
        self.executed = True
        self._prepare_generation()
        try:
            self.before_generation()
            log_debug("Generating profile '" + self.name + "'.")
            self.generate()
            log_debug("Successfully generated profile '" + self.name + "'.")
            self.after_generation()
        except Exception as err:
            if isinstance(err, CustomError):
                raise
            msg = "An unkown error occured in your generate() function: "
            self._gen_err(msg + type(err).__name__ + ": " + str(err))
        finally:
            self._cleanup_generation()
        return self.result

    def _prepare_generation(self):
        pass

    def _cleanup_generation(self):
        pass

    def before_generation(self):
        pass

    def after_generation(self):
        pass

    def _gen_err(self, msg):
        """A wrapper to raise a :class:`~errors.GenerationError` with the
        profilename.
        """
        raise GenerationError(msg, profile=self.name)

    def check_cycle(self, profile=None):
        if profile is None:
            profile = self
        if profile.parent is not None:
            same_name = profile.parent.name == self.name
            return same_name or self.check_cycle(profile.parent)
        return False

    def save_child_data(self):
        self.child_data = {
            "parent": self
        }

    def generate_subprofile(self, profilename, extend_data=None):
        if profilename == self.name:
            self._gen_err("Recursive profiles are forbidden!")
        elif profilename in const.args.exclude:
            log_debug("'" + profilename + "' is in exclude list." +
                      " Skipping generation of profile...")
        else:
            # Create data for subprofile
            self.save_child_data()
            if extend_data is not None:
                data = extend_data(self.child_data)
            # Create instance of profilename with merged options
            # and current directory
            profile = ProfileLoader().new_object(profilename, data)
            # Generate profile and add it to this profile's
            # generation result
            self.result["profiles"].append(profile.start_generation())


# Abstract class that implements useful stuff for all profiles
class EventProfile(BaseProfile):
    # TODO: these are class variables, so they would be shared between all instances
    beforeInstall = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed before the profile gets installed for the first time.
    """

    beforeUpdate = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed before the profile gets updated and only if the profile was
    already installed.
    """

    beforeUninstall = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed before the profile gets uninstalled.
    """

    afterInstall = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed after the profile gets installed for the first time.
    """

    afterUpdate = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed after the profile gets updated and only if the profile was
    already installed.
    """

    afterUninstall = None
    """This field can be implemented/set by the user. This has to be a string
    or a function that return a string. The string will be stored as shell
    script (only if it doesn't equal the last script stored) and will be
    executed after the profile gets uninstalled.
    """

    prepare_script = None
    """This field can be set by the user. This has to be a string and will be
    prepended to the event scripts of this profile or any of its subprofiles.
    """
    def getscriptattr(self, event_name):
        # Get event property
        attribute = getattr(self, event_name, None)
        if attribute is None:
            return None
        # Check for correct type
        if isinstance(attribute, str):
            return attribute
        if callable(attribute):
            # If attribute is a function we need to execute it safely and
            # make sure that it returns a string
            try:
                returnval = attribute()
            except Exception as err:
                err_name = type(err).__name__
                msg = event_name + " exited with error " + err_name
                self._gen_err(msg + ": " + str(err))
            # Again type checking
            if isinstance(returnval, str):
                return returnval
            self._gen_err(event_name + "() needs to return a string")
        self._gen_err(event_name + " needs to be a string or function")

    def generate_script(self, event_name, script):
        def get_prepare_scripts(profile=self, profilename=self.name):
            result = ""
            # First check if prepare_script is available and is a string
            if profile.prepare_script is not None:
                if isinstance(profile.prepare_script, str):
                    # Save prepare_script as result
                    result = profile.prepare_script
                else:
                    self._gen_err("prepare_script of " + profilename +
                                  " needs to be a string.")
            # Prepend prepare_scripts of parents to result
            if profile.parent is not None:
                result = get_prepare_scripts(profile.parent, profilename) + result
            return result
        # Change dir automatically if enabled and the main script doesn't
        # start with a cd command
        if const.settings.smart_cd and not script.strip().startswith("cd "):
            dir_ = self.cwd if hasattr(self, "cwd") else ""
            if hasattr(self, "options") and not dir_:
                dir_ = self.options["directory"]
            if not dir_:
                msg = "'smart_cd' is activated, but this profile doesn't have"
                msg += " any 'directory'-property to switch to."
                log_warning(msg)
            else:
                script = "\ncd " + self.options["directory"] + "\n" + script
        # Prepend prepare_scripts
        script = get_prepare_scripts() + "\n" + script
        # Prettify script a little bit
        pretty_script = ""
        start = 0
        end = 0
        i = 0
        for line in script.splitlines():
            line = line.strip()
            if line:
                if start == 0:
                    start = i
                end = i
            pretty_script += line + "\n"
            i += 1
        # TODO use beautysh here for even prettier scripts
        # Remove empty lines at beginning and end of script
        pretty_script = "\n".join(pretty_script.splitlines()[start:end+1])
        # Build path where the script will be stored
        script_dir = os.path.join(const.internal.session_dir, "scripts")
        makedirs(script_dir)
        script_name = self.name + "_" + event_name
        script_path = script_dir + "/" + script_name
        script_path += "_" + md5(pretty_script) + ".sh"
        # Write new script to file
        if not os.path.exists(script_path):
            try:
                script_file = open(script_path, "w")
                script_file.write(pretty_script)
                script_file.close()
            except IOError:
                self._gen_err("Could not write file '" + script_path + "'")
            log_debug("Generated script '" + script_path + "'")
        else:
            log_debug("Script already generated at '" + script_path + "'")
        return md5(pretty_script)

    def before_generation(self):
        """Generates event scripts from attributes. Stores them as shell
        scripts if they changed.

        Raises
            :class:`~errors.GenerationError`: One of the attributes isn't a
                string nor a function that returned a string
        """

        log_debug("Generating event scripts for profile '" + self.name + "'.")
        events = [
            "beforeInstall", "beforeUpdate", "beforeUninstall",
            "afterInstall", "afterUpdate", "afterUninstall"
        ]
        for event in events:
            script = self.getscriptattr(event)
            if script is not None:
                script_hash = self.generate_script(event, script)
                self.result[event] = script_hash


# Pythonic profile
class Profile(EventProfile):
    def __init__(self, name, data):
        super().__init__(name, data)
        self.options = deepcopy(dict(const.defaults.items()))
        if "options" in self.data:
            self.options.update(deepcopy(self.data["options"]))

    def save_child_data(self):
        super().save_child_data()
        self.child_data["options"] = deepcopy(self.options)

    def _make_read_opt(self, kwargs):
        """Creates a function that looks up options but prefers options of
        kwargs.

        Args:
            kwargs (dict): kwargs of a command
        Returns:
            function: A function that looks up and returns the value for a key
            in kwargs. If the key is not in kwargs it uses
            :attr:`self.options<Profile.options>` for look up.
        """
        def read_opt(opt_name):
            if opt_name in kwargs:
                return kwargs[opt_name]
            return self.options[opt_name]
        return read_opt

    @staticmethod
    def autofind(func):
        def decorated(self, target, *args, **kwargs):
            if isinstance(target, str):
                target = self.find(target)
                if target is None:
                    read_opt = self._make_read_opt(kwargs)
                    if not read_opt("optional"):
                        self._gen_err("Couldn't find target '" + target + "'.")
                    else:
                        return None
                else:
                    return func(self, target, *args, **kwargs)
            elif isinstance(target, AbstractFile):
                return func(self, target, *args, **kwargs)
            else:
                self._gen_err("Unexpexted type of target")
        return decorated

    @staticmethod
    def autocopy(func):
        def decorated(self, target, *args, **kwargs):
            read_opt = self._make_read_opt(kwargs)
            if isinstance(target, str):
                copied = StaticFile.new(
                    os.path.basename(target),
                    source=target,
                    origin=read_opt("directory")
                )
                return func(self, copied, *args, **kwargs)
            elif isinstance(target, AbstractFile):
                return func(self, target, *args, **kwargs)
            else:
                self._gen_err("Unexpexted type of target")
        return decorated

    def find(self, target):
        """Find a dotfile in :const:`~const.target_files`. Depends on the
        current set tags.

        This can be overwritten to change the searching behaviour of a profile.
        Furthermore it can be used by the user to just find a dotfile without
        linking it directly.

        Args:
            target (str): A filename, without preceding tag
        Raises:
            :class:`~errors.GenerationError`: More than one file was found
        Return:
            str: The full path of the file or ``None`` if no file was found
        """
        try:
            found_target = find_target_with_tags(target, self.options["tags"])
            if not found_target:
                found_target = find_target_exact(target)
            return found_target
        except ValueError as err:
            self._gen_err(err)

    def replace_target_name(self, target, **kwargs):
        read_opt = self._make_read_opt(kwargs)
        replace_pattern = read_opt("replace_pattern")
        if not replace_pattern:
            msg = "You are trying to use 'replace', but no "
            msg += "'replace_pattern' was set."
            self._gen_err(msg)
        base = os.path.basename(target)
        base = strip_hashs(strip_tags(base))
        return re.sub(replace_pattern, read_opt("replace"), base)

    def build_link_name(self, target, **kwargs):
        read_opt = self._make_read_opt(kwargs)
        # First generate the correct name for the symlink
        replace = read_opt("replace")
        name = read_opt("name")
        if replace:  # When using regex pattern, name property is ignored
            name = self.replace_target_name(target, **kwargs)
        elif name:
            name = normpath(name)
        else:
            # "name" wasn't set by the user,
            # so fallback to use the target name (but without the tag or hash)
            name = os.path.basename(strip_hashs(strip_tags(target)))
        # Add prefix and suffix to name
        base, ext = os.path.splitext(os.path.basename(name))
        if read_opt("extension"):
            ext = "." + read_opt("extension")
        name = os.path.join(os.path.dirname(name), read_opt("prefix") +
                            base + read_opt("suffix") + ext)
        return name

    def build_link_path(self, target, **kwargs):
        read_opt = self._make_read_opt(kwargs)
        return abspath(
            self.build_link_name(target, **kwargs),
            origin=read_opt("directory")
        )

    def build_link(self, abstractfile, **kwargs):
        target = abstractfile.getpath()
        path = self.build_link_path(target, **kwargs)
        self.add_link(path, target, abstractfile.get_buildup_data(), **kwargs)

    def add_link(self, path, target, buildup=None, **kwargs):
        read_opt = self._make_read_opt(kwargs)
        linkdata = GenLinkData()
        linkdata["path"] = path
        linkdata["target"] = target
        linkdata["target_inode"] = os.stat(target).st_ino
        linkdata["owner"] = read_opt("owner")
        linkdata["permission"] = read_opt("permission")
        linkdata["secure"] = read_opt("secure")
        linkdata["hard"] = read_opt("hard")
        linkdata["buildup"] = buildup
        self.result["links"].append(linkdata)


class CommandProfile(Profile):
    def __init__(self, name, data):
        self._old_builtins = {}
        self.custom_builtins = {}
        self.builtins_overwritten = False
        super().__init__(name, data)
        # Create commands from functions
        for attr_name in dir(self):
            if attr_name.startswith("command_"):
                self.create_command(attr_name[8:], self.__getattribute__(attr_name))

    def __set_builtins(self):
        """Maps functions from :const:`custom_builtins` to builtins,
        so commands don't need to be called using ``self`` everytime.
        """
        if self.builtins_overwritten:
            raise FatalError("Builtins are already overwritten")
        for funcname in self.custom_builtins:
            if funcname in builtins.__dict__:
                self._old_builtins[funcname] = builtins.__dict__[funcname]
            builtins.__dict__[funcname] = self.custom_builtins[funcname]
        self.builtins_overwritten = True

    def __reset_builtins(self):
        """Restores old Builtin mappings."""
        if not self.builtins_overwritten:
            raise FatalError("Builtins weren't overwritten yet")
        for key, val in self._old_builtins.items():
            builtins.__dict__[key] = val
        self.builtins_overwritten = False

    def _prepare_generation(self):
        self.__set_builtins()

    def _cleanup_generation(self):
        self.__reset_builtins()

    def create_command(self, func_name, func):
        """Adding this decorator to a function will make it available
        in :func:`generate()` as a builtin.

        Furthermore this adds some documentation to the function.

        Args:
            func (function): The function that will become a command
        """
        # Check that we don't accidentally shadow an real builtin
        if func_name in original_builtins:
            msg = func_name
            msg += "() is a builtin and therefore can't be a command."
            raise GenerationError(msg)
        # # Add documentation to function
        # docs = func.__doc__.split("\n\n")
        # new_doc = docs[0]
        # new_doc += "\n\n        .. note:: "
        # new_doc += "This function is a command. It can be called "
        # new_doc += "without the use of ``self`` within :func:`generate()`."
        # for i in range(1, len(docs)):
        #     new_doc += "\n\n" + docs[i]
        # func.__doc__ = new_doc
        # Add function to custom builtins
        self.custom_builtins[func_name] = func


# The current profile
class EasyProfile(CommandProfile):
    def __init__(self, name, data):
        super().__init__(name, data)
        self.owd = None
        self.cwd = data.get("cwd", None)
        if not self.cwd:
            self.cwd = self.options["directory"]

    def save_child_data(self):
        super().save_child_data()
        self.child_data["cwd"] = self.cwd

    def build_link_path(self, target, **kwargs):
        read_opt = self._make_read_opt(kwargs)
        return abspath(
            self.build_link_name(target, **kwargs),
            origin=abspath(read_opt("directory"), origin=self.cwd)
        )
    # TODO find a proper location for choose-functions, etc

    def command_find(self, target):
        """Find a dotfile in :const:`~const.target_files`. Depends on the
        current set tags.

        This can be overwritten to change the searching behaviour of a profile.
        Furthermore it can be used by the user to just find a dotfile without
        linking it directly.

        Args:
            target (str): A filename, without preceding tag
        Raises:
            :class:`~errors.GenerationError`: More than one file was found
        Return:
            str: The full path of the file or ``None`` if no file was found
        """
        return super().find(target)

    @Profile.autofind
    @Profile.autocopy
    def command_decrypt(self, target):
        """Creates an :class:`~dynamicfile.EncryptedFile` instance from a
        target, updates and returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        Args:
            target(str/:class:`~dynamicfile.DynamicFile`): The target file that
                will be used as source of the
                :class:`~dynamicfile.EncryptedFile`
        Returns:
            :class:`~dynamicfile.EncryptedFile`: The dynamic file that holds
            the decrypted target
        """
        return EncryptedFile.new(target.name, source=target, origin=self.cwd)

    def command_merge(self, name, targets, **kwargs):
        """Creates a :class:`~dynamicfile.SplittedFile` instance from a list of
        targets, updates and returns it.

        The target can be either just the name of a file that will be searched
        for or it can be another dynamic file that already provides a generated
        file.

        Args:
            targets(list): The list of targets that will be used as
                source of the :class:`~dynamicfile.SplittedFile`
        Returns:
            :class:`~dynamicfile.SplittedFile`: The dynamic file that holds the
            merged target
        """
        if len(targets) < 2:
            self._gen_err("merge() for '" + name + "' needs at least "
                          + "two dotfiles to merge")
        read_opt = self._make_read_opt(kwargs)
        sources = []
        for target in targets:
            if isinstance(target, str):
                found_target = self.find(target)
                if found_target:
                    copied = StaticFile.new(
                        os.path.basename(target),
                        source=found_target,
                        origin=self.cwd
                    )
                    sources.append(copied)
                elif not read_opt("optional"):
                    self._gen_err("Couldn't find target '" + target + "'.")
            elif isinstance(target, AbstractFile):
                sources.append(target)
            else:
                self._gen_err("Unexpexted type of target")
        return SplittedFile.new(name, source=sources, origin=self.cwd)

    @Profile.autofind
    @Profile.autocopy
    def command_pipe(self, target, shell_command):
        """Creates a :class:`~dynamicfile.FilteredFile` instance from a target,
        updates and returns it.

        Args:
            target(str/:class:`~dynamicfile.DynamicFile`): The target file that
                will be used as source of the
                :class:`~dynamicfile.FilteredFile`
            shell_command (str): The shell command that the content of target
                will be piped into
        Returns:
          :class:`~dynamicfile.FilteredFile`: The dynamic file that holds the
          output of the shell command
        """
        params = {
            "source": target,
            "shell_command": shell_command,
            "origin": self.cwd
        }
        return FilteredFile.new(target.name, **params)

    def command_link(self, *targets, **kwargs):
        """Link one ore more targets with current options.

        Args:
            *targets (list): One ore more targets that shall be linked. Targets
                can be just file names or any dynamic files.
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: One of the targets were not found
        """
        for target in targets:
            self.single_link(target, **kwargs)

    @Profile.autofind
    @Profile.autocopy
    def single_link(self, target, **kwargs):
        self.build_link(target, **kwargs)

    def command_extlink(self, path, **kwargs):
        """Link any file specified by its absolute path.

        Args:
            path (str): The path of the target
            **kwargs (dict): A set of options that will be overwritten just
                for this call
        """
        read_opt = self._make_read_opt(kwargs)
        path = os.path.join(self.cwd, expandpath(path))
        if os.path.exists(path):
            self.add_link(self.build_link_path(path, **kwargs), path, **kwargs)
        elif not read_opt("optional"):
            self._gen_err("Target path '" + path +
                          "' does not exist on your filesystem!")

    def generate_targetlist(self, target_pattern, match_path=False, fullmatch=True, choose_files=None):
        if choose_files is None:
            choose_files = self.choose_first_tag
        if fullmatch:
            matcher = re.fullmatch
        else:
            matcher = re.search
        target_list = []
        target_dir = {}
        # Find all files that match target_pattern and index
        # them by there name without tag
        for fullpath in walk_dotfiles():
            name = os.path.basename(fullpath)
            tags = get_tags_from_path(name)
            basename = strip_tags(name)
            if match_path:
                path = fullpath
            else:
                path = basename
            match = matcher(target_pattern, path)
            if match is not None:
                if basename not in target_dir:
                    target_dir[basename] = []
                target_dir[basename].append((tags, fullpath))
        # Then choose which files will be returned
        for base, files in target_dir.items():
            target_list += choose_files(basename, files)
        return target_list

    def choose_first_tag(self, basename, files):
        # Go through set tags and take the first file that matches a tag
        for tag in self.options["tags"]:
            for item in files:
                for tmp_tag in item[0]:
                    if tmp_tag == tag:
                        return [item[1]]
        # Look for files without tags
        no_tag = None
        for item in files:
            if not item[0]:
                if no_tag is None:
                    no_tag = item
                else:
                    msg = "There are two targets found with the same name:"
                    msg += " '" + basename + "'\n  " + no_tag[1]
                    msg += "\n  " + item[1]
                    self._gen_err(msg)
        if no_tag is not None:
            return [no_tag[1]]
        return []

    def choose_all(self, basename, files):
        return [item[1] for item in files]

    def command_links(self, target_pattern, match_path=False, encrypted=False, **kwargs):
        """Calls :func:`link()` for all targets matching a pattern.

        Furthermore it allows to ommit the ``replace_pattern`` in favor of the
        ``target_pattern`` and to decrypt matched files first.

        Args:
            target_pattern (str): The regular expression that matches the file
                names
            encrypted (bool): True, if the targets shall be decrypted
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: No files or multiple file with
                the same name were found with this pattern
        """
        read_opt = self._make_read_opt(kwargs)
        target_list = []
        target_dir = {}

        # Use target_pattern as replace_pattern
        if read_opt("replace") and not read_opt("replace_pattern"):
            kwargs["replace_pattern"] = target_pattern

        # Find all files that match target_pattern
        target_list = self.generate_targetlist(
            target_pattern, match_path,
            choose_files=self.choose_all if match_path else self.choose_first_tag
        )

        # Now we have all targets and can create links for each one
        if not target_list and not read_opt("optional"):
            self._gen_err("No files found that would match the"
                          + " pattern: '" + target_pattern + "'")
        else:
            create_link = Profile.autocopy(self.build_link)
            for target in target_list:
                name = os.path.basename(target)
                file = StaticFile.new(name, source=target, origin=self.cwd)
                if encrypted:
                    file = EncryptedFile.new(name, source=file, origin=self.cwd)
                self.build_link(file, **kwargs)

    def command_cd(self, directory=None):
        """Sets :attr:`self.directory<Profile.directory>`. Unix-like cd.

        The ``directory`` can be an absolute or relative path and it expands
        environment variables.

        Args:
            directory (str): The path to switch to
        """
        if directory is None:
            self.owd = self.cwd
            self.cwd = const.defaults.directory
        elif directory == "-":
            self.owd, self.cwd = self.cwd, self.owd
        else:
            self.owd = self.cwd
            self.cwd = os.path.join(self.cwd, expandpath(directory))
        self.command_opt(directory=self.cwd)

    def command_default(self, *options):
        """Resets :attr:`self.options<Profile.options>` back to
        :const:`constants.DEFAULTS`. If called without arguments,
        it resets all options and tags.

        Args:
            *options (list): A list of options that will be reset
        """
        if not options:
            self.options = deepcopy(dict(const.defaults.items()))
        else:
            for item in options:
                self.options[item] = const.defaults.get(item).value

    def command_rmtags(self, *tags):
        """Removes a list of tags.

        Args:
            tags (list): A list of tags that will be removed
        """
        for tag in tags:
            if self.command_has_tag(tag):
                self.options["tags"].remove(tag)

    def command_tags(self, *tags):
        """Adds a list of tags.

        Args:
            tags (list): A list of tags that will be added
        """
        for tag in tags:
            if tag not in self.options["tags"]:
                self.options["tags"].append(tag)

    def command_has_tag(self, tag):
        """Returns true if a tag is set.

        Args:
            tag (str): A tag that will be checked for
        Returns:
            bool: True, if tag is set
        """
        return tag in self.options["tags"]

    def command_opt(self, **kwargs):
        """Sets options permanently. The set options will be used in all future
        calls of commands and subprofiles as long as the commands don't
        override them temporarily.

        Args:
            **kwargs: A set of options that will be set permanently
        Raises:
            :class:`~errors.GenerationError`: One of to be set option does
                not exist
        """
        for key in kwargs:
            if key in self.options:
                self.options[key] = kwargs[key]
            else:
                self._gen_err("There is no option called " + key)

    def command_subprof(self, *profilenames, **kwargs):
        """Executes a list of profiles by name.

        Args:
            *profilenames(list): A list of profilenames that will be executed
            **kwargs (dict): A set of options that will be overwritten just for
                this call
        Raises:
            :class:`~errors.GenerationError`: Profile were executed in a
                cycly or recursively
        """
        def bake_options(data):
            data["options"] = {**data["options"], **kwargs}
            return data

        for subprofile in profilenames:
            self.generate_subprofile(subprofile, extend_data=bake_options)


# Profile that loads the result from a static dictionary using EasyProfile
# semantics. The syntax is as follows:
# generate:                           # {
#   - link:                           #   "generate": [
#       - abc                         #     { "link": ["abc", "efg"] },
#       - efg                         #     { "link": ["xyz"] },
#   - link:                           #     { "link": [
#       - xyz                         #         { "pipe": ["file", "command"]},
#   - link:                           #         "uvw"
#       - pipe:                       #       ]
#           - file                    #     }
#           - command                 #   ]
#       - uvw                         # }
class EasyParsedProfile(EasyProfile):
    def __init__(self, name, data, parsed=None):
        super().__init__(name, data)
        if parsed is None:
            raise UberdotError("parsed must be set")
        self.parsed = parsed

    def _prepare_generation(self):
        super()._prepare_generation()
        self.beforeUpdate = parsed["beforeUpdate"]
        self.beforeInstall = parsed["beforeInstall"]
        self.beforeUninstall = parsed["beforeUninstall"]
        self.afterUpdate = parsed["afterUpdate"]
        self.afterInstall = parsed["afterInstall"]
        self.afterUninstall = parsed["afterUninstall"]

    def generate(self):
        # TODO: Error handling
        for command in self.parsed["generate"]:
            self.exec_command(command)

    def exec_command(self, commanddict):
        name, params = commanddict.items()[0]
        name = "command_" + name
        evalued_params = []
        for param in params:
            if isinstance(param, dict):
                evalued_params.append(self.exec_command(param))
            else:
                evalued_params.append(param)
        return self.custom_builtins[name](**evalued_params)


# Profile that loads the result from a static dictionary
class StaticParsedProfile(ProfileSkeleton):
    def __init__(self, name, data, parsed=None):
        super().__init__(name, data)
        if parsed is None:
            raise UberdotError("parsed must be set")
        self.parsed = parsed

    def start_generation(self):
        try:
            log_debug("Reading parsed profile '" + self.name + "'.")
            self.generate()
            log_debug("Successfully read profile '" + self.name + "'.")
        except Exception as err:
            if isinstance(err, CustomError):
                raise
            msg = "An unkown error occured when reading parsed profile: "
            self._gen_err(msg + type(err).__name__ + ": " + str(err))
        return self.result

    def generate(self):
        # TODO: Error handling
        for link in self.parsed["links"]:
            self.result["links"].append(link)
        for profile in self.parsed["profiles"]:
            name = profile["name"]
            obj = StaticParsedProfile.new(name, self.data, parsed=profile)
            self.result["profiles"].append(obj.start_generation())
        self.result["beforeUpdate"] = parsed["beforeUpdate"]
        self.result["beforeInstall"] = parsed["beforeInstall"]
        self.result["beforeUninstall"] = parsed["beforeUninstall"]
        self.result["afterUpdate"] = parsed["afterUpdate"]
        self.result["afterInstall"] = parsed["afterInstall"]
        self.result["afterUninstall"] = parsed["afterUninstall"]
