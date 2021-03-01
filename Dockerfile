###########
# Builder #
###########
FROM python:3.8.8-slim AS builder

# This is where pip will install to
ENV PYROOT /pyroot
# A convenience to have console_scripts in PATH
ENV PYTHONUSERBASE $PYROOT

WORKDIR /build

# Setup virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
COPY requirements/prod.txt ./

# Install build dependencies
RUN apt-get update && \
  apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --upgrade --no-cache-dir pip wheel && \
  pip install --require-hashes -r prod.txt

####################
# Production image #
####################
FROM python:3.8.8-slim

# Dependencies path
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy dependencies from build container
COPY --from=builder /opt/venv /opt/venv

# Copy source code
COPY . ./

# Start application
ENTRYPOINT ["python", "main.py"]
