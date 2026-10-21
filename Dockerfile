# GameDock runs on the official Ownfoil image: it brings the runtime (Python packages,
# nstools) and GameDock replaces the application code. OWNFOIL_BASE is the Ownfoil
# release this code is based on; keep it in step with the UPSTREAM file.
ARG OWNFOIL_BASE=2.5.0
FROM a1ex4/ownfoil:${OWNFOIL_BASE}

RUN rm -rf /app && mkdir -p /app/data
COPY app/ /app/
COPY i18n /tmp/i18n
COPY locales /tmp/locales
RUN chmod +x /app/run.sh \
    && python3 /tmp/i18n/localize.py /app /tmp/locales \
    && rm -rf /tmp/i18n /tmp/locales
