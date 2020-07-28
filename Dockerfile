FROM python:3.8-alpine

COPY requirements.txt /tmp
RUN apk add --no-cache postgresql-libs postgresql-dev alpine-sdk unzip && pip install -r /tmp/requirements.txt && apk del postgresql-dev alpine-sdk
RUN cd /tmp && wget https://github.com/fredex42/gnmvidispine/archive/master.zip && unzip master.zip && cd gnmvidispine-master && pip install -r requirements.txt && python ./setup.py install && cd ~ && rm -rf /tmp/gnmvidispine
COPY src/dist/gnm-assetsweeper-3.0.tar.gz /tmp
RUN cd /tmp && tar xvzf gnm-assetsweeper-3.0.tar.gz && cd gnm-assetsweeper-3.0 && python ./setup.py install && cd ~ && rm -rf /tmp/assetsweeper
RUN adduser -u 504 -D assetimporter
USER assetimporter
WORKDIR /home/assetimporter