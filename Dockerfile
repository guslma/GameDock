# GameDock: the official Ownfoil image, renamed and in several languages
ARG OWNFOIL_VERSION=latest
FROM a1ex4/ownfoil:${OWNFOIL_VERSION}

COPY build /tmp/gamedock/build
COPY locales /tmp/gamedock/locales
RUN python3 /tmp/gamedock/build/build.py /app /tmp/gamedock/locales \
    && rm -rf /tmp/gamedock
