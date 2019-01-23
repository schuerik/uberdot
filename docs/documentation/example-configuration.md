This is an example of a more complex configuration that tries to show of most features of dotmanager and what you 
could achieve with inheritance. It's a variation of a setup I'm using for over a half year now. 
The tags that I defined have the following semantics:
* **arch:** An Arch linux based distribution is installed
* **antergos:** An Arch linux based distribution is installed
* **debian:** An Debian based distribution is installed
* **master:** The device is powerful and should be fullfeatured
* **minimal:** The device is a low-end-device and most features should be disabled
* **private:** This my own device with private data and access to my local network
* **office:** A device used for work
* **laptop:** This device is a laptop
* **asus:** A concrete asus laptop of mine
* **asus:** A concrete thinkpad laptop of mine 
* **small:** This device has a small monitor

First I created some profiles that represent my current setup. Any device that I want to use this setup on inherits from it. These profiles define the programs that should be configured and link some platform specific configs.
``` python
# This profile is the base for all devices that use my current setup
class Main(Profile):
    def generate(self):
        tags("arch", "master")
        if info.distribution() == "Antergos":
            tags("antergos")
        subprof("Git", "I3", "Bash", "Zsh", "Vim")

        link("pacman.conf", directory="/etc")


# This profile contains configs that I only want on my private devices. It inherits from the Main profile.
class Private(Main):
    def generate(self):
        tags("private")
        super().generate()

        # File synchronisation
        link("unison_data.prf", name=".unison/data.prf")
       
        cd("/etc")
        link("hosts", "mkinitcpio.conf")
        links("\d{2}-\w+\.rules", directory="udev/rules.d")
```

Then there are profiles for my different devices. `Pi` and `Server` doesn't inherit from `Main` so they will define subprofiles as well. The other profiles are used to link configs that configure hardware. These profiles (except for  `Laptop`) are the only profiles that I install as a root profile. 
``` python
# This profile contains configs that I use on all of my laptops
class Laptop(Profile):
    def generate(self):
        link("hdmi_plugin.sh")
        cd("/etc/NetworkManager")
        link("sshOnConnect.sh", directory="dispatcher.d")

        # Wifi profiles
        cd("system-connections")
        opt(permission=600)
        links("wifi-(.+).gpg", replace=r"\1", encrypted=True)


# This is an asus laptop of mine
class Asus(Private):
    def generate(self):
        tags("asus", "small", "laptop")
        super().generate()
        subprof("Laptop")


# This is an thinkpad laptop of mine
class Thinkpad(Private):
    def generate(self):
        tags("thinkpad", "small", "laptop")  
        super().generate()
        subprof("Laptop")
        link("alsa-base.conf", directory="/etc/modprobe.d/")


# This is my device at the office
class Office(Main):
    def generate(self):
        tags("office")
        super().generate()


# A raspberry pi I use as mini server
class Pi(Profile):
    def generate(self):
        tags("pi", "debian", "minimal")
        subprof("Git", "Bash", "Vim", "Radicale")


# A more powerful webserver
class Server(Profile):
    def generate(self):
        tags("debian", "master")
        subprof("Git", "Bash", "Vim")
```

At last there are the profiles for the individual programs that I called as subprofiles above. Most of the links are defined here.
``` python
class Bash(Profile):
    def generate(self):
        opt(prefix=".")
        link("bashrc", "inputrc")
        link("bashrc", "inputrc", directory="/root")
        link("bash_profile", name=".bash_profile")
        opt(prefix=".bash_")
        link("sensitiverc", "basicrc", "systemrc")
        link("sensitiverc", "basicrc", "systemrc", directory="/root")
        link("customrc", optional=True)


class Zsh(Profile):
    def generate(self):
        link("zshrc", prefix=".")
        link("zsh_profile", name=".zprofile")
        opt(prefix=".zsh_")
        link("sensitiverc", "basicrc", "systemrc")
        link("customrc", optional=True)


class Git(Profile):
    def generate(self):
        link("gitconfig", prefix=".")
        link("gitconfig_system", name="/etc/gitconfig")


class I3(Profile):
    def generate(self):
        subprof("Rofi", "Polybar")

        cd(".config/i3")
        link("i3config", name="config")
        link("lock.sh", "lock.png")

        link("dunstrc", directory="../dunst")

        cd("$HOME")
        link("wallpaper.sh")
        link("compton.conf", prefix=".")


class Rofi(Profile):
    def generate(self):
        cd(".config/rofi")
        links("rofi-(.+\.rasi)", replace=r"\1")


class Polybar(Profile):
    def generate(self):
        cd(".config/polybar")
        link("polybarconfig", "polybarlaunch.sh", replace_pattern="polybar(.+)", replace=r"\1")
        link("pkg.sh")


class Vim(Profile):
    def generate(self):
        # Configs
        links("g?vimrc", prefix=".")
        cd(".vim")
        links("\w+\.vim")

        # Documentation
        link("my.txt", directory="doc")

        # Snippets
        links(".+\.snippets", directory="UltiSnips")

        # Spellfiles
        links(".+\..+\.add(\.spl)?", directory="spell")

        # Configs loaded after plugins
        link("vim-gitgutter.vim", directory="after/plugin")
        link("vim-illuminate.vim", directory="after/plugin")


class Radicale(Profile):
    def generate(self):
        cd(".config")
        link("radicale.conf", name="radicale/config")
        link("radicale_log.conf", name="radicale/log_config")
        link("radicale.service", directory="systemd/user")
```
You could argue that some programs doesn't need an extra profile like `Polybar` and `Rofi` because those would have fit in `I3` as well. It's fine to do so, however by encapsulating their configs in their own profile you increase the re-usability of a configuration. 