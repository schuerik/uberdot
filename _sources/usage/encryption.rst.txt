**********
Encryption
**********

uberdot can decrypt dotfiles using OpenPGP.


Decryption used in a profile
============================

Decryption is possible by either using the ``decrypt()`` command or by
using the encryption flag of the ``links()`` command (see more in the
commands section).


Manual encryption
=================

.. code:: bash

   gpg -c path/to/file
   # or
   gpg -c path/to/file -o path/to/output


Manual decryption
=================

.. code:: bash

   gpg -d path/to/file
