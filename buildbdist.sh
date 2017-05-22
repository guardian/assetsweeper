#!/bin/bash -e

echo ----------------------------
echo Performing Python build
echo ----------------------------

cd src
python ./setup.py bdist
if [ ! -d "~/rpmbuild" ]; then
    mkdir -p ~/rpmbuild
fi

for x in `ls dist/*.tar.gz`; do cp "$x" ~/rpmbuild/assetsweeper.tar.gz; done
HASH=$(shasum -a 256 "assetsweeper.tar.gz" | cut -d ' ' -f 1)
echo -e "sha256=$HASH" > assetsweeper.tar.gz.sha

aws s3 cp ~/rpmbuild/assetsweeper.tar.gz s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.tar.gz --acl public-read
aws s3 cp assetsweeper.tar.gz.sha s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.tar.gz.sha --acl public-read
