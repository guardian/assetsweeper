#!/usr/bin/env bash -e

echo ----------------------------
echo Packaging zip
echo ----------------------------

cd ~
cd ~
zip -r assetsweeper-${CIRCLE_BUILD_NUM}.zip assetsweeper/
aws s3 cp assetsweeper-${CIRCLE_BUILD_NUM}.zip s3://gnm-multimedia-deployables/asset_folder_importer/${CIRCLE_BUILD_NUM}/assetsweeper-${CIRCLE_BUILD_NUM}.zip --acl public-read
