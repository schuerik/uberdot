Testing uberdot
==================

To verify that uberdot is working correct and behaves the same on all
platforms, there are regression tests in  `test/regression/test.py`. At the
moment some features can't be tested but the testing suit will be extended in the
future eventually.

For now all regression tests can only check if uberdot manipulated a
directory tree correctly. Those are ``DirRegressionTest``. There is also a base
class ``RegressionTest`` that does nothing more than checking a precondition,
executing uberdot with some specific parameters and checking a post
condition. If both conditions are met and uberdot exited with exitcode, the test
is successful. The special ``DirRegressionTest`` takes a dictionary as condition
that describes the expected directory tree. There is also ``OutputRegressionTest``
which checks a directory tree as precondition, suppresses the output of uberdot
and ignores the postcondition. Those are used to simply test if features like
``--debuginfo`` raise errors.


Environments
------------

Regression tests can use different environments as starting directory instead of
$HOME, depending on their save file. E.g. A regression test with ``--save update``
will use `test/regression/environment-update` instead of
`test/regression/environment-default` as starting directory and
`test/regression/profile_update` instead of `test/regression/profile` as source
directory for profiles. The environment will be reset before and after every test
using git.

Current environments are:
    - **environment-default**: No profile is installed. Contains only one file
      that shall be untouched by uberdot.
    - **environment-update**: ``DirOption`` is pre-installed. Also contains one
      file that shall be untouched.
    - **environment-nested**: ``SuperProfileTags`` and its subprofiles are
      installed. Also contains one file that shall be untouched.


Creating testenvironment
^^^^^^^^^^^^^^^^^^^^^^^^

1. Create a new directory called `environment-<name>` in `test/regression/`
2. Set ``directory`` and ``profileFiles`` in `test/regression/regressiontest.ini`
   for your new environment
3. Install one or multiple profiles into the environment using `regressiontest.ini`
   as config and ``--save <name>``. Also set ``--verbose`` because the config will
   suppress the output of uberdot:

   .. code:: bash

        $ cd test/regression
        $ ../../udot.py -vi --config regressiontest.ini --save update ProfileName

4. Because uberdot stores only absolute paths in the installed-file, you will have
   to modify `test/regression/data/installed/<name>.json` manually, replacing all
   absolute paths with relative paths
5. To match the installed-file, all symlinks in the environment also need to be
   modified by you to use relative paths:

   .. code:: bash

        $ cd environment-update
        $ ln -sf ../files/name1 name1

6. Remember to commit everything before executing a test on the new or modified
   environment because otherwise all changes will be reset


Creating testcases
------------------

Create a new test case with:

.. code:: python

    newtest = DirRegressionTest(name_of_test,
                                additional_cli_arguments,
                                precondition,
                                postcondition,
                                environment)

And either expect it to be successful:

.. code:: python

    newtest.success()

Or fail with a specific cause of failure:

.. code:: python

    newtest.fail(phase, cause)


Phases
^^^^^^

There are three phases of a regression test in which the test can fail:

    - pre: The precondition is checked
    - run: uberdot is executed
    - post: The postcondition is checked

If a test fails, it fails with a cause. For the "pre" and "post" phase the cause
is a specific error message. For "run" it is the non-zero exitcode of uberdot.


Pre- and postcondition for DirRegressionTest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

DirRegressionTests take two dictionaries that describe the directory tree of
`test/regression/environment-<name>`. The dictionary looks like this:

.. code:: python

    {
        ".": {
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
        "b": {...},
        "b/c": {...},
    }

The keys of the top dictionary are the relative paths from
`test/regression/environment-<name>` for any subdirectory that you want to
verify. For every subdirectory there are the keys ``files``, ``links``,
``permission``, ``rootuser`` and ``rootgroup``. The last three describe the
subdirectory itself. All of those keys are optional. Because we can't create
new users/groups just for the sake of this test, we only distinguish between
normal and root users/groups. ``files`` and ``links`` are both lists of
dictionaries that we use to describe all files in the subdirectory. Both have
the keys ``name`` (which is the name of the file/symlink), ``permission``,
``rootuser`` and ``rootgroup``. There is also the optional key ``content``
which hold the md5 hash of the files content. The difference between those two
lists is, that ``links`` has dictionaries with an additional ``target`` key
that specifies a links target relatively to `test/regression/`. Also all files
that are listed in ``links`` will be verified to be a symbolic link, where as
files that are listed in ``files`` must not be a symbolic link.

Defaults:
    - **permission**: Won't be tested
    - **rootuser**: False
    - **rootgroup**: False
    - **content**: Won't be tested
