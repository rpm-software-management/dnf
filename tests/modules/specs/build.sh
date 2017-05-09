#!/bin/bash


# run this script to (re-)generate module repos


# Requirements:
#  * createrepo_c
#  * rpmbuild


export LC_ALL=C

set -e


DIR=$(dirname $(readlink -f $0))
ARCHES="i686 x86_64 s390x"
rm -rf $DIR/../modules
mkdir -p $DIR/../modules

for module in $DIR/*-*-*; do
    module_name=$(basename $module)
    for spec in $module/*.spec; do
        echo
        echo "Building $spec..."
        for target in $ARCHES; do
            rpmbuild --quiet --target=$target -ba --nodeps --define "_srcrpmdir $DIR/../modules/$module_name/src" --define "_rpmdir $DIR/../modules/$module_name/" $spec
        done
    done
done


# include noarch RPMs into arch dirs to get them included in module metadata
for module in $DIR/*-*-*; do
    module_name=$(basename $module)
    repo_path_noarch=$DIR/../modules/$module_name/noarch

    for target in $ARCHES; do
        repo_path=$DIR/../modules/$module_name/$target
        if [ -d $repo_path_noarch ]; then
            cp -a $repo_path_noarch/* $repo_path/
        fi
    done
done


./_create_modulemd.py


for module in $DIR/*-*-*; do
    module_name=$(basename $module)
    for target in $ARCHES; do
        repo_path=$DIR/../modules/$module_name/$target
        repo_path_all=$DIR/../modules/_all/$target

        mkdir -p $repo_path_all
        cp -a $repo_path/* $repo_path_all/

        createrepo_c $repo_path
        ./_createrepo_c_modularity_hack.py $repo_path
    done
done


for target in $ARCHES; do
    repo_path=$DIR/../modules/_all/$target
    createrepo_c $repo_path
    ./_createrepo_c_modularity_hack.py $repo_path
done


echo "DONE: Test data created"
