#!/usr/bin/env bash -e

echo ----------------------------
echo Performing Python build
echo ----------------------------

cd src
python ./setup.py bdist
if [ ! -d "~/rpmbuild" ]; then
    mkdir -p ~/rpmbuild
fi

for x in `ls dist/*.tar.gz`; do cp "$x" ~/rpmbuild/assetsweeper.tar.gz; done
aws s3 cp ~/rpmbuild/assetsweeper.tar.gz s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.tar.gz --acl public-read
