#!/bin/bash -e

function increment_release {
    FILENAME=$1

    RELEASEVER=$(grep '%define release' ${FILENAME} | awk -F ' ' '{print $3}')
    if [ "${CIRCLE_BUILD_NUM}" != "" ]; then
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
echo Packaging RPM
echo ----------------------------

mkdir -p ${HOME}/rpmbuild/SOURCES
cd src
python ./setup.py sdist
mv dist/*.tar.gz ${HOME}/rpmbuild/SOURCES
cd .. #FIXME: replace with calculated abs path of script

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
    HASH=$(shasum -a 256 "$x" | cut -d ' ' -f 1)
    echo -e "sha256=$HASH" > assetsweeper.rpm.sha
    aws s3 cp "$x" s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/`basename $x` --acl public-read
    aws s3 cp assetsweeper.rpm.sha s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/`basename $x`.sha --acl public-read
    if [ "$?" != "0" ]; then
        exit $?
    fi
done