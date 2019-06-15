### Start this script from the root directory of the repository
if [ -z $(ls | grep "udot.py") ]; then
    echo "Started from the wrong direcory. Use ./test/test-version.sh"
    exit 69
fi

# Settings
master_dir="uberdot-master"

# Helpers
cleanup() {
    rm -rf $master_dir
}

exitsuccess() {
    cleanup
    echo "ok."
    exit 0
}

exiterror() {
    cleanup
    >&2 echo "You need to increment the version number!!"
    exit 1
}


# Get version numbers
version_pr=$(./udot.py --config test/versiontest.ini --version | cut -d' ' -f2)

echo "Fetching master..."
# To test/debug this script offline, create a bundle of the repository with:
#   git bundle create dm.bundle --all
# and use this git clone instead:
#   git clone dm.bundle --branch master --single-branch $master_dir &> /dev/null
git clone https://github.com/schuerik/uberdot.git --branch master --single-branch $master_dir &> /dev/null
version_master=$($master_dir/udot.py --config test/versiontest.ini --version | cut -d' ' -f2)

echo "PullRequest version: $version_pr"
echo "Master version: $version_master"

# Version compare
if (( "$(echo $version_pr | cut -d'.' -f1)" > "$(echo $version_master | cut -d'.' -f1)" )); then
    exitsuccess
else
    if (( "$(echo $version_pr | cut -d'.' -f1)" < "$(echo $version_master | cut -d'.' -f1)" )); then
        exiterror
    else
        if (( "$(echo $version_pr | cut -d'.' -f2)" > "$(echo $version_master | cut -d'.' -f2)" )); then
            exitsuccess
        else
            if (( "$(echo $version_pr | cut -d'.' -f2)" < "$(echo $version_master | cut -d'.' -f2)" )); then
                exiterror
            else
                version_pr=$(echo $version_pr | cut -d'.' -f3)
                version_master=$(echo $version_master | cut -d'.' -f3)
                if (( "$(echo $version_pr | cut -d'_' -f1)" > "$(echo $version_master | cut -d'_' -f1)" )); then
                    exitsuccess
                else
                    if (( "$(echo $version_pr | cut -d'_' -f2)" > "$(echo $version_master | cut -d'_' -f2)" )); then
                        >&2 echo "When you increment the schema version you need to increment the normal version number as well!"
                    fi
                    exiterror
                fi
            fi
        fi
    fi
fi
