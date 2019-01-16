Dotmanager can decrypt dotfiles using OpenPGP. To do so you need to encrypt the dotfile by yourself:
``` bash
gpg -c path/to/file
# or
gpg -c path/to/file -o path/to/output
```
Decryption is also possible via commandline:
``` bash
gpg -d path/to/file
```

