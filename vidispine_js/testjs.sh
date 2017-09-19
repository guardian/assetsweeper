#!/usr/bin/env bash

if [ "${VIDISPINE_HOST}" == "" ]; then
    VIDISPINE_HOST="localhost"
fi
if [ "${VIDISPINE_PORT}" == "" ]; then
    VIDISPINE_PORT="8080"
fi
if [ "${VIDISPINE_USER}" == "" ]; then
    VIDISPINE_USER="admin"
fi
if [ "${VIDISPINE_PASSWORD}" == "" ]; then
    VIDISPINE_PASSWORD="admin"
fi

if [ "$1" == "" ]; then
    TEST_SCRIPT="@force_close_file.js"
else
    TEST_SCRIPT="@$1"
fi

curl -D- -X POST -u ${VIDISPINE_USER}:${VIDISPINE_PASSWORD} http://${VIDISPINE_HOST}:${VIDISPINE_PORT}/API/javascript/test --header "Content-Type: application/javascript" -d ${TEST_SCRIPT}
echo
