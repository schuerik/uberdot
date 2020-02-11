#!/usr/bin/env bash

##########################################################################################
# This script is only for deployment purposes. It won't work, if not executed by travis! #
##########################################################################################

if [ -z $TRAVIS ]; then
    echo "This is no travis build. Aborting."
    exit 69
fi

if [ "$TRAVIS_BRANCH" != "master" ]; then
    echo "Not on master, skipping..."
    exit 0
fi

# Settings
master_dir="uberdot-master"
deploy_dir="./deploy"
# Set the clone url to use ssh
git remote set-url origin git@github.com:schuerik/uberdot.git


# Check if manpage is up-to-date (so we now that travis won't update it afterwards)
git_status="$(git status --porcelain -- docs/sphinx/build/man | head -c 2 | tail -c 1)"
if [[ $git_status != "M" ]] && [[ $git_status != "A" ]]; then
    # Check if version was incremented
    git clone https://github.com/schuerik/uberdot.git --branch master --single-branch $master_dir &> /dev/null
    version_master=$($master_dir/udot.py --config $deploy_dir/autotagging.ini --version | cut -d' ' -f2)
    version_latest=$(git log --tags --simplify-by-decoration --pretty="format:%d" | grep tag | head -n1 | cut -d'v' -f2 | head -c -2 | cut -d',' -f1)
    echo "Master version: $version_master"
    echo "Latest release: $version_latest"
    # Set tag if version differs
    if [[ $version_latest != $version_master ]]; then
        git config --local user.name "Erik Schulz"
        git config --local user.email "archlinuxuser@protonmail.com"
        tag="v$version_master"
        git tag $tag || exit 2
        GIT_SSH_COMMAND="ssh -i $deploy_dir/github-key -F /dev/null" git push origin $tag || exit 3
        echo "Created tag: $tag"
    else
        echo "The current version is already tagged."
    fi
else
    echo "Waiting for travis to update manpage..."
fi
