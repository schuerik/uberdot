#!/usr/bin/env bash

##########################################################################################
# This script is only for deployment purposes. It won't work, if not executed by travis! #
##########################################################################################

if [ -z $TRAVIS ]; then
    echo "This is no travis build. Aborting."
    exit 69
fi

# Set the clone url to use ssh
git remote set-url origin git@github.com:RickestRickSanchez/dotmanager.git
# Commit and push the built manpage to the repo
git add docs/sphinx/build/man || exit 1
if [ "$(git status --porcelain -- docs/sphinx/build/man | head -c 1)" == "M" ]; then
    git commit -m "updated manpage" || exit 2
    GIT_SSH_COMMAND="ssh -i github-key -F /dev/null" git push origin HEAD:master || exit 3
    echo "Updated manpage."
else
    echo "Manpage didn't change..."
fi
