FROM centos:7.4.1708

USER root
RUN yum -y install epel-release
RUN yum -y groupinstall 'Development Tools' && yum -y install python3 which sudo postgresql-server python3-pip && yum -y clean all && rm -rf /var/cache/yum
RUN pip3 install virtualenv nose pep8 awscli && rm -rf ~/.cache/pip3
RUN adduser ci -u 1001
COPY dockersetup/ci_sudoers /etc/sudoers.d/ci
RUN chown root /etc/sudoers.d/ci && chmod 440 /etc/sudoers.d/ci
USER ci
WORKDIR /home/ci