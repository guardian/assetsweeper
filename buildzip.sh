#!/bin/bash -e

echo ----------------------------
echo Packaging zip
echo ----------------------------

cd ~

zip -r assetsweeper-${CIRCLE_BUILD_NUM}.zip assetsweeper/
HASH=$(shasum -a 256 "assetsweeper-${CIRCLE_BUILD_NUM}.zip" | cut -d ' ' -f 1)
echo -e "sha256=$HASH" > assetsweeper-${CIRCLE_BUILD_NUM}.zip.sha
aws s3 cp assetsweeper-${CIRCLE_BUILD_NUM}.zip s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.zip --acl public-read
aws s3 cp assetsweeper-${CIRCLE_BUILD_NUM}.zip.sha s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.zip.sha --acl public-read