FROM 855023211239.dkr.ecr.eu-west-1.amazonaws.com/guardianmultimedia/pluginsbuild:3

USER root
RUN yum -y install which postgresql; yum -y clean all; rm -rf /var/cache/yum
RUN pip install virtualenv nose pep8; rm -rf ~/.cache/pip
RUN adduser ci
USER ci
WORKDIR /home/ci