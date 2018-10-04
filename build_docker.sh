#!/bin/bash -e

ABSOLUTE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo Running from ${ABSOLUTE_PATH}

cd src
python ./setup.py sdist --formats=gztar

cd ${ABSOLUTE_PATH}

docker build . -t andyg42/assetsweeper:${CIRCLE_BUILD_NUM}
docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}
docker push andyg42/assetsweeper:${CIRCLE_BUILD_NUM}