#!/usr/bin/env bash

function increment_release {
    FILENAME=$1

    RELEASEVER=$(grep '%define release' ${FILENAME} | awk -F ' ' '{print $3}')
    if [ ${CIRCLE_BUILD_NUM} != "" ]; then
        NEWVER=${CIRCLE_BUILD_NUM}
    else
        NEWVER=$(($RELEASEVER+1))
    fi
    echo Release version was ${RELEASEVER}, now is ${NEWVER}
    cat ${FILENAME} | sed "s/\%define release .*/%define release ${NEWVER}/" > ${FILENAME}.new
    mv ${FILENAME} ${FILENAME}.old
    mv ${FILENAME}.new ${FILENAME}
}

echo ----------------------------
echo Performing Python build
echo ----------------------------

cd src
python ./setup.py bdist
if [ ! -d "~/rpmbuild" ]; then
    mkdir -p ~/rpmbuild
fi

for x in `ls dist/*.tar.gz`; do cp "$x" ~/rpmbuild/assetsweeper.tar.gz; done

echo ----------------------------
echo Packaging RPM
echo ----------------------------

cd ..
SPECFILE=assetsweeper.spec
increment_release assetsweeper.spec

if [ "${CIRCLE_BUILD_NUM}" == "" ]; then
    CIRCLE_BUILD_NUM=dev
fi

if [ "${VIRTUAL_ENV}" != "" ]; then
    deactivate
fi

RPM_BASE=$(grep '%define name' ${SPECFILE} | awk -F ' ' '{print $3}')
PATH=/usr/bin:/bin:/usr/local/bin
rpmbuild -bb ${SPECFILE}

if [ "$?" != "0" ]; then
    exit $?
fi

for x in `ls ${HOME}/rpmbuild/RPMS/noarch/${RPM_BASE}*.rpm`; do
    aws s3 cp "$x" s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/`basename $x` --acl public-read
    if [ "$?" != "0" ]; then
        exit $?
    fi
done