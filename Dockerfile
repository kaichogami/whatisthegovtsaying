FROM node:22-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY scripts/requirements.txt /app/scripts/
RUN pip3 install --break-system-packages -r /app/scripts/requirements.txt

# Install Node deps
COPY package.json package-lock.json /app/
RUN npm ci

# Copy project
COPY . /app/

# Make scripts executable
RUN chmod +x scripts/build_and_deploy.sh

# Persistent volume for digests.db
VOLUME /app/data

# Entrypoint: run immediately, then loop daily at 07:00 UTC
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
