# Contributing Guide

Everyone is encouraged to contribute to this project. You can contribute by
[proposing new features](https://github.com/schuerik/uberdot/issues/new?assignees=&labels=enhancement&template=feature_request.md&title=),
[submitting a bug](https://github.com/schuerik/uberdot/issues/new?assignees=&labels=bug&template=bug_report.md&title=),
improving the documentation (see [documentation](https://schuerik.github.io/uberdot/developers/documentation.html))
or by helping me programming.



## Code Contributions

If you want to modify the code, you need to follow some rules or I won't accept
your pull requests. Exceptions are possible but need to be justified.


### Coding style

All code contributions should follow the [Google styleguide](https://github.com/google/styleguide/blob/gh-pages/pyguide.md) and
[PEP8](https://www.python.org/dev/peps/pep-0008/) the best way possible. I highly recommend using pylint (although it's not
perfect) to check if your modifications are PEP8 conform. ~~If you don't do this, the PR will be automatically rejected by
CodeFactor. In this case you should fix the issues that CodeFactor found and update your PR.~~
In the future PRs will be automatically rejected if they violate PEP8.


### Documenting

Whenever you modify the functionality of uberdot, a single function/class or add completely new functionality, you have to
update the documentation. Most documentation updates will be very simple, because they only require an update of the reference
manual which is generated automatically from the doc strings in the code. Yow can find a section about the google doc string syntax
[here](https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings). But if you
modify or add bigger features, you should verify if you have to update the user guide. Take a look at
[documentation](https://schuerik.github.io/uberdot/developers/documentation.html) for more information about the
documentation system.


### Versioning

Always remember to increment the version number before you submit a pull
request. Given the version number ``MILESTONE.MAJOR.PATCH_SCHEMA`` increment

- **MILESTONE** when the pr solves a milestone goal
- **MAJOR** when the pr adds a new feature
- **PATCH** when the pr solves a bug or changes documentation
- **SCHEMA** when the pr makes a change to installed file schema

You can set the version number in ``uberdot/constants.py``
