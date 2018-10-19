FROM centos:7

RUN yum -y install epel-release && yum -y install postgresql-dev python python-pip unzip wget vim file && yum clean all && rm -rf /var/cache/yum
COPY src/dist/gnm-assetsweeper-3.0.tar.gz /tmp
COPY requirements.txt /tmp

RUN cd /tmp && wget https://github.com/fredex42/gnmvidispine/archive/master.zip && unzip master.zip && cd gnmvidispine-master && pip install -r requirements.txt && python ./setup.py install && cd ~ && rm -rf /tmp/gnmvidispine
RUN cd /tmp && tar xvzf gnm-assetsweeper-3.0.tar.gz && cd gnm-assetsweeper-3.0 && pip install -r /tmp/requirements.txt && python ./setup.py install && cd ~ && rm -rf /tmp/assetsweeper
RUN rpm --erase unzip wget
RUN adduser assetimporter -u 504
USER assetimporter
WORKDIR /home/assetimporter