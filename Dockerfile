FROM centos:7

RUN yum -y install epel-release && yum -y install postgresql-dev python python-pip file && yum clean all && rm -rf /var/cache/yum
COPY src/dist/gnm-assetsweeper-3.0.tar.gz /tmp
COPY requirements.txt /tmp

RUN cd /tmp && tar xvzf gnm-assetsweeper-3.0.tar.gz && cd gnm-assetsweeper-3.0 && pip install -r /tmp/requirements.txt && python ./setup.py install && cd ~ && rm -rf /tmp/assetsweeper
RUN adduser assetimporter
USER assetimporter
WORKDIR /home/assetimporter