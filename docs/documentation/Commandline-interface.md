This document explains all commandline options in detail.

The general syntax is:
```
dotmgr.py [--directory DIRECTORY] [-d] [--dui] [-f] [-m] [--option KEY=VAL [KEY=VAL ...]] [--parent PARENT]
          [-p] [--save SAVE] [--superforce] [-v] (-h | -i | -u | -s | --version) [profiles [profiles ...]]
```

There are 5 modes of which you have to specify exactly one:

| Mode                | Description                                                                                   |
|---------------------|-----------------------------------------------------------------------------------------------|
| -h, --help          | Shows a short help message with all options and modes and exits                               |
| --version           | Shows the version of dotmanager and exits                                                     |
| -i, --install       | Installs every specified profile. If a profile is already installed it will be updated instead of installed. |
| -u, --uninstall     | Uninstalls every specified profile. If a profile is not installed, dotmanager will skip this profile. |
| -s, --show          | Shows information about installed profiles and links. If you specify `profiles` this will show only information about those profiles. Otherwise information about all installed profiles will be shown. |


You can also choose a couple of optional arguments:

| Option                         | Description                                                                        |
|--------------------------------|------------------------------------------------------------------------------------|
| --directory DIRECTORY          | Overwrites the default directory temporarily                                       |
| -d, --dry-run                  | Simulates the changes dotmanager would perform if executed without this flag       |
| --dui                          | Use an alternative startegy to install profiles and links. The default strategy will do this by recursively go through the profiles and create/update all links one by one. This can cause conflicts if e.g. a link is moved from one to another profile. This strategy installs links by first doing all removals, then all updates and last all new installs. Most conflicts should be solved by this strategy but it has the downside that the output isn't that clear as the normal strategy. |
| -f, --force                    | Overwrites files that already exists in your filesystem with your links            |
| -m, --makedirs                 | Makes directories if they don't exist. Any directory created inherits the owner of its parent directory. |
| --option KEY=VAL [KEY=VAL ...] | Let you temporarily overwrite the option section of your config file               |
| --parent PARENT                | Forces the profiles that you install/update to be installed as subprofile of PARENT. This should be only needed to solve certain conflicts. |
| --plain                        | Prints the `DiffLog` unformatted and exits. Only used for debugging purpose.       |
| -p, --pretty-print             | Prints out the changes that dotmanager would perform if executed without this flag. This differs from `--dry-run` in that way that it won't do any checks on the profiles or filesystem, so `--dry-run` is almost always to prefer. The only use-case is if your profiles will raise an error and aborts but you want to now what would have happen to get a better understanding of the issue in your profile/workflow itself.|
| --save SAVE                    | Use another `installed-file` for this execution. Can be used to install profiles multiple times on the same device. But be carefully not fuck up your other installations of those profiles! This is mostly useful if you want to test the linking process in another directory or if those profiles are installed in completely different locations of your device |
| --superforce                   | Overwrites files and links that are blacklisted because it is considered dangerous to overwrite those files e.g. `/etc/hosts` or `/etc/passwd` |
| -v, --verbose                  | Shows a stacktrace when an error occurs                                            |

`profiles` is a space seperated list of profiles. Any profile will be identified by its class name, not by its filename. Don't forget that python class names are case-sensitive.
