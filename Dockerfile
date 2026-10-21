# GameDock image, built from the official Python image: nothing here depends on the
# Ownfoil image. Same runtime as Ownfoil 2.5.0: Python 3.14 on Alpine, with the packages
# pinned in requirements.lock.
FROM python:3.14.8-alpine3.24

ARG TARGETPLATFORM
COPY requirements.txt requirements.lock /tmp/
# armv6/armv7 have no prebuilt wheels for some packages: compile them, then drop the compilers
RUN apk add --no-cache bash sudo \
    && if [ "$TARGETPLATFORM" = "linux/arm/v6" ] || [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
        apk add --no-cache --virtual .build build-base gcc musl-dev jpeg-dev zlib-dev libffi-dev; \
    fi \
    && pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/requirements.lock \
    && if [ "$TARGETPLATFORM" = "linux/arm/v6" ] || [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
        apk del .build; \
    fi \
    && rm /tmp/requirements.txt /tmp/requirements.lock

COPY app/ /app/
COPY i18n /tmp/i18n
COPY locales /tmp/locales
RUN mkdir -p /app/data \
    && chmod +x /app/run.sh \
    && python3 /tmp/i18n/localize.py /app /tmp/locales \
    && rm -rf /tmp/i18n /tmp/locales

WORKDIR /app
ENTRYPOINT [ "/app/run.sh" ]
