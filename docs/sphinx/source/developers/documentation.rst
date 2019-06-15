=======================
How to document uberdot
=======================

The documentation, reference manual and manpage of uberdot are all generated with
Sphinx_. It consists of mainly two big parts. First the reference manual, which
is generated from the source code, and second the user guides which are generated
from the sphinx source directory.

You will find most information on how to write documentation with Sphinx in
their own documentation. This document covers only how Sphinx is set up in this
project and explains the building process.


Structure / Set up
==================

- Sphinx is located at ``docs/sphinx/``.
- All user guides are located at ``docs/sphinx/source/usage/``
- All developer guides (except for CONTRIBUTING.md) are located at
  ``docs/sphinx/source/developers/``
- The theme was modified to hide or highlight some information in the reference
  manual with ``docs/sphinx/source/custom.css``
- Sphinx is configured to use the autodoc, m2r, napoleon and github pages plugin
- The contributing guide is converted from markdown to restructered text using m2r
- The navigation of the theme is overridden by ``docs/sphinx/source/_templates/navigation.html``
- The built html documentation can be found in ``docs/sphinx/build/html/``
- The built man page can be found in ``docs/sphinx/build/man/``
- The man page is built from a subset of user guides


Generating documentation
========================

To generate the documentation locally on your device you will need to install Sphinx,
m2r and the autodoc plugin. To do so, you can use pip:

.. code:: bash

    $ pip install sphinx autodoc m2r

Then you can build the documentation with:

.. code:: bash

    $ cd docs/sphinx
    $ make html

And open it directly in your favorite web browser:

.. code:: bash

    $ firefox build/html/index.html

The same goes for the man page:

.. code:: bash

    $ cd docs/sphinx
    $ make man

    $ man -l build/man/uberdot.1

If you delete or rename file you might want to do a clean up of the build directory:

.. code:: bash

    $ cd docs/sphinx

    $ make clean-html  # Clean only the html build
    $ make clean-man  # Clean only the man page build

    $ make clean  # Clean all builds


Deploying
=========

The documentation and man page will be automatically generated when you create a pull
request to verify if it builds without errors. When your pull request is merged
into master, Travis will deploy ``docs/sphinx/build/html/`` to the gh-pages branch,
which is used to host the documentation.
If there are changes to the man page, Travis will commit and push them to the master.

Note: While the man page build is tracked/checked into git, the html documentation is
not checked in and only available at the gh-pages branch.


.. _Sphinx: http://www.sphinx-doc.org/en/master/index.html
