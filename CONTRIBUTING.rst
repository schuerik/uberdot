==================
Contributing Guide
==================

Everyone is encouraged to contribute to this project. You can contribute by
`proposing new features`_, `submitting a bug`_, improving the documentation
(see :doc:`documentation`) or by helping me programming.



Code Contributions
==================

If you want to modify the code, you need to follow some rules or I won't accept
your pull requests. Exceptions are possible but need to be justified.


Coding style
------------

All code contributions should follow the `Google styleguide`_ and `PEP8`_ the
best way possible. I highly recommend using pylint (although it's not perfect)
to check if your modifications are PEP8 conform. If you don't do this, the PR
will be automatically rejected by CodeFactor. In this case you should fix the
issues that CodeFactor found and update your PR.


Documenting
-----------

Whenever you modify the functionality of Dotmanager, a single function/class or
add completely new functionality, you have to update the documentation. Most
documentation updates will be very simple, because they only require an update
of the reference manual which is generated from the doc strings in the code.
Yow can find a section about the doc string syntax in the `Google styleguide`_.
But if you modify or add bigger features, you should verify if you have to
update the user guide. Take a look at `documentation`_ for more information
about the documenation system.


Versioning
----------

Always remember to increment the version number before you submit a pull
request. Given the version number ``MILESTONE.MAJOR.PATCH_SCHEMA`` increment
the:

    - MILESTONE when the pr solves a milestone goal
    - MAJOR when the pr adds a new feature
    - PATCH when the pr solves a bug
    - SCHEMA when the pr makes a change to installed file schema

You will find the version number in ``dotmanager/constants.py``


.. _proposing new features: https://github.com/RickestRickSanchez/dotmanager/issues/new?assignees=&labels=enhancement&template=feature_request.md&title=
.. _submitting a bug: https://github.com/RickestRickSanchez/dotmanager/issues/new?assignees=&labels=bug&template=bug_report.md&title=
.. _Google styleguide: https://github.com/google/styleguide/blob/gh-pages/pyguide.md
.. _PEP8: https://www.python.org/dev/peps/pep-0008/
.. _documentation: https://rickestricksanchez.github.io/dotmanager/developers/documentation.html
