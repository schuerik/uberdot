Testing uberdot
==================

To verify that uberdot is working correct and behaves the same on all
platforms, there are regression tests in  ``test/regressiontest.py``. At the
moment they are far away from being complete but will be extended in the
future.

For now all regression tests can only check if uberdot manipulated a
directory tree correctly. Those are ``DirRegressionTest``. There is also a base
class ``RegressionTest`` that does nothing more than checking a precondition,
executing uberdot with some specific parameters and checking a post
condition. If both conditions are met, the test is successful. The special
``DirRegressionTest`` takes a dictionary as condition that describes the
expected directory tree.

All profiles that are used in the tests can be found in ``test/profiles/``, all
dotfiles in ``test/files``. uberdot will be executed with
``test/environment`` as default directory and all profiles must not define
links outside of this directory. Otherwise the tests could overwrite existing
setups.


Creating testcases
------------------

Create a new test case with:

.. code:: python

    newtest = DirRegressionTest(name_of_test,
                                additional_cli_arguments,
                                precondition,
                                postcondition,
                                clean_environment)

And either expect it to be successful:

.. code:: python

    newtest.success()

Or fail with a specific cause of failure:

.. code:: python

    newtest.fail(phase, cause)


Phases
------

There are three phases of a regression test in which the test can fail:

    - pre: The precondition is checked
    - run: uberdot is executed
    - post: The postcondition is checked

If a test fails, it fails with a cause. For the "pre" and "post" phase the cause
is a specific error message. For "run" it is the non-zero exitcode of uberdot.


Pre- and postcondition for DirRegressionTest
--------------------------------------------

DirRegressionTests take two dictionaries that describe the directory tree of ``test/``.
The dictionary looks like this:

.. code:: python

    {
        "environment": {
            "files": [
                {
                    "name": "name.bla",
                    "permission": 600,
                    "rootuser": True,
                    "rootgroup": True,
                    "content": "b37b8487ac0b8f01e9e34949717b16d1"
                }
            ],
            "links": [
                {
                    "name": "name.bla1",
                    "target": "files/name1",
                    "permission": 600,
                    "rootuser": True,
                    "rootgroup": True,
                    "content": "b37b8487ac0b8f01e9e34949717b16d1"
                },
                {
                    "name": "test.link",
                    "target": "files/test",
                    "permission": 777,
                    "rootuser": False,
                    "rootgroup": False
                }
            ],
            "permission": 777,
            "rootuser": True,
            "rootgroup": True
        },
        "environment/b": {...},
        "environment/b/c": {...},
    }

The keys of the top dictionary are the relative paths from ``test/`` for any
subdirectory that you want to verify. For every subdirectory there are the keys ``files``, ``links``, ``permission``, ``rootuser``
and ``rootgroup``. The last three describe the subdirectory itself. Because we can't create new users/groups
just for the sake of this test, we only distinguish between normal and root users/groups.
``files`` and ``links`` are both lists of dictionaries that we use to describe all files in the subdirectory.
Both have the keys ``name`` (which is the name of the file/symlink), ``permission``, ``rootuser`` and ``rootgroup``.
There is also the optional key ``content`` which hold the md5 hash of the files content.
The difference between those two lists is, that ``links`` has dictionaries with an additional ``target`` key that
specifies a links target relatively to ``test/``. Also all files that are listed in ``links`` will be verified to be
a symbolic link, where as files that are listed in ``files`` must not be a symbolic link.
