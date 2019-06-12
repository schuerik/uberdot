==========
.dotignore
==========


When you are already familiar with git, you probably already know what a .dotignore-file is about, although this works a little different.


A .dotignore-file is used to specify files that Dotmanager will ignore and therefore won't link. The file needs to be placed at the top of
your dotfiles repository and contains in each line a `regular expression <https://docs.python.org/3.7/howto/regex.html>`_ that will be matched
against the absolute path of every file in your dotfiles repository. If a pattern matches, that file will be ignored.
