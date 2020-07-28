#!/bin/bash -e

ABSOLUTE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo Running from ${ABSOLUTE_PATH}

cd src
python ./setup.py sdist --formats=gztar

cd ${ABSOLUTE_PATH}

if [ "${CIRCLE_BUILD_NUM}" != "" ]; then
    DOCKER_VERSION=${CIRCLE_BUILD_NUM}
else
    DOCKER_VERSION=dev
fi

docker build . -t andyg42/assetsweeper:${DOCKER_VERSION}
docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}
#docker push andyg42/assetsweeper:${DOCKER_VERSION}