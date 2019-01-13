All code contributions should follow the [Google styleguide](https://github.com/google/styleguide/blob/gh-pages/pyguide.md) 
and [PEP8](https://www.python.org/dev/peps/pep-0008/) the best way possible. I highly recommend using pylint (altough it's
not perfect). Furthermore [Type Hints](https://www.python.org/dev/peps/pep-0484/) need to be added to every function or method
you create. 

If you find old code that does not follow the guide lines (but for a good reason exceptions are allowed), please fix this code in 
seperate commit.

Last but not least remember to imcrement the version number before you submit a pull request. Given the version number 
MILESTONE.MAJOR.PATCH_SCHEMA increment the:
* MILESTONE when the pr solves a milestone goal
* MAJOR when the pr adds a new feature
* PATCH when the pr solves a bug
* SCHEMA when the pr makes a change to installed file
