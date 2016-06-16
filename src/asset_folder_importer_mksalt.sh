#!/bin/bash

#this copies source files to the arrangement needed to apply to a
#saltstack tree

OUTDIR="salt/asset_folder_importer"

if [ -d "${OUTDIR}" ]; then
	echo Output directory ${OUTDIR} exists, not over-writing. Please move or remove ${OUTDIR} to continue.
	exit 1
fi

echo Outputting to \"${OUTDIR}\"...
mkdir -p "${OUTDIR}/files"

echo Copying package directory...
cp -r asset_folder_importer "${OUTDIR}/files"

echo Copying scripts...
cp "asset_folder_sweeper.py" "${OUTDIR}/files"
cp "prelude_importer.py" "${OUTDIR}/files"
cp "asset_folder_vsingester.py" "${OUTDIR}/files"
cp "asset_folder_importer.cfg" "${OUTDIR}/files"
cp "premiere_get_referenced_media.py" "${OUTDIR}/files"
cp "asset_folder_verify_files.py" "${OUTDIR}/files"
cp "asset_permissions.pl" "${OUTDIR}/files"

echo Copying states...
cp asset_folder_importer.sls "${OUTDIR}"/init.sls
cp asset_folder_database.sls "${OUTDIR}"/database.sls

echo Done.
