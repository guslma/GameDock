# GameDock: the official Ownfoil image, renamed and in several languages
ARG OWNFOIL_VERSION=latest
FROM a1ex4/ownfoil:${OWNFOIL_VERSION}

COPY build /tmp/gamedock/build
COPY locales /tmp/gamedock/locales
COPY branding /tmp/gamedock/branding
RUN python3 /tmp/gamedock/build/build.py /app /tmp/gamedock/locales /tmp/gamedock/branding \
    && rm -rf /tmp/gamedock
