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


# Workflow explained on an example
Suppose you have the following profile:
``` python
class Main(Profile):
    def generate():
        link(decrypt("test.txt"))
```
The first time that you install this profile `decrypt()` will search for the file "text.txt" in your repository, decrypt it and
calculate it's hash (in this example bb6a0d9da197de74db91745fb9b433e1). It then writes the decrypted file to
* data/decrypted/test.txt#bb6a0d9da197de74db91745fb9b433e1
and
* data/decrypted/test.txt#bb6a0d9da197de74db91745fb9b433e1.bak
Dotmanager will later link to "data/decrypted/test.txt#bb6a0d9da197de74db91745fb9b433e1".
Now every time this link is updated or removed, Dotmanager will check if the calculated hash differs from the current installed
hash and if so warn you that you could lose changes. To help you write back the changes to the original file it gives you the
following options:
* Abort: abort the installation/removal process to fix changes manually
* Diff: displays a diff of the changes and lets you decide again what to do
* Ignore: ignore the warning. The link will be updated/removed but the changes to the old dynamicfile will stay.
* Patch: write a git diff of the changes to a desired location. In some cases you can apply it to the original directly with git
* Undo: discards all changes made to the file and proceed with updating/removing the link


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
Instead of using the absolute path to the dotfile you could use `self.find()` of the profile to find the file automatically
``` python
from dotmanager.dynamicfile import EncryptedFile

encrypt = EncryptedFile("test.txt")
encrypt.add_source(self.find("test.txt"))
encrypt.update()
```
