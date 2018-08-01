#!/bin/bash


# run this script to (re-)generate module repos


# Requirements:
#  * createrepo_c
#  * rpmbuild


export LC_ALL=C

set -e


DIR=$(dirname $(readlink -f $0))
ARCHES="x86_64"
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
            cp $repo_path_noarch/* $repo_path/ || :
        fi
    done
done


for spec in $DIR/_non-modular/*.spec; do
    echo
    echo "Building NON-MODULAR $(basename $spec)..."
    for target in $ARCHES; do
        rpmbuild --quiet --target=$target -ba --nodeps --define "_srcrpmdir $DIR/../modules/_non-modular/src" --define "_rpmdir $DIR/../modules/_non-modular/" $spec
    done
done


repo_path_noarch=$DIR/../modules/_non-modular/noarch
for target in $ARCHES; do
    repo_path=$DIR/../modules/_non-modular/$target
    if [ -d $repo_path_noarch ]; then
        cp $repo_path_noarch/* $repo_path/ || :
    fi
done


$DIR/_create_modulemd.py


for target in $ARCHES; do
    cp $DIR/../defaults/httpd.yaml $DIR/../modules/httpd-2.4-1/$target/
done

for module in $DIR/*-*-* $DIR/_non-modular; do
    module_name=$(basename $module)
    for target in $ARCHES; do
        repo_path=$DIR/../modules/$module_name/$target
        repo_path_all=$DIR/../modules/_all/$target

        mkdir -p $repo_path_all
        cp $repo_path/* $repo_path_all/ || :

        createrepo_c $repo_path
        if [ "_non-modular" != "$module_name" ]
        then
          $DIR/_createrepo_c_modularity_hack.py $repo_path
        fi
    done
done


for target in $ARCHES; do
    repo_path=$DIR/../modules/_all/$target
    createrepo_c $repo_path
    $DIR/_createrepo_c_modularity_hack.py $repo_path
done


echo "DONE: Test data created"
