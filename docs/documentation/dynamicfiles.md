Dynamicfiles are used whenever one or more dotfiles need to be altered before they are symlinked. Because the original shall not
be altered by Dotmanager, Dotmanager processes the specified dotfiles and stores the altered version in a subdirectory of
`data/`. There are different types of dynamicfiles, each one using their own subdirectory:
* `data/decrypted`: dotfiles that were decrypted
* `data/merged`: dotfiles that were merged from multiple dotfiles

To make use of a dynamicfile you can either use one of the helper commands like `decrypt()` or `merge()` which will return a
dynamicfile or create an instance of a dynamicfile by yourself for more advanced usage (see the example at the bottom).
Every time you do this, the dynamicfile will be updated immediately (even if you only do a dry-run) and the generated result
will be written to the corresponding subdirectory.

Because the generated file that will be linked is now outside of your repository, the repository is obviously not able to track
changes anymore. Also editing a symlink to this file won't update the original dotfiles in your repository. To circumvent this
disadvantage, Dotmanager will track changes that you apply to the symlinked generated file and warns you if you would overwrite
those changes when you install a profile. To do so, Dotmanager appends the md5 hash of the file to its filename and stores a
backup file next to it. That way changes won't be lost and Dotmanager can calculate a diff for you if you like.


# Creating an instance of a dynamicfile manually
``` python
from dotmanager.dynamicfile import EncryptedFile

# Create an instance of EncryptedFile with the name "test.txt"
encrypt = EncryptedFile("test.txt")
# Add the source files that shall be processed (in this case its only one)
encrypt.add_source("~/dotfile_repo/test.txt")
# Update the dynamicfile to process the source and write the resulting file
encrypt.update()
```
Instead of using the absolute path to the dotfile you could use for example `find_exact_target()` from dotmanager.utils
``` python
from dotmanager.utils import find_exact_target
from dotmanager.dynamicfile import EncryptedFile

encrypt = EncryptedFile("test.txt")
encrypt.add_source(find_exact_target("test.txt"))
encrypt.update()
```
