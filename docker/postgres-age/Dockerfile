FROM postgres:16-bookworm

ARG AGE_TAG=PG16/v1.6.0-rc0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        flex \
        bison \
        git \
        libreadline-dev \
        zlib1g-dev \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${AGE_TAG}" https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && make PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config install \
    && rm -rf /tmp/age
