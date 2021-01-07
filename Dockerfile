###########
# Builder #
###########
FROM python:3.8.7-slim AS builder

# This is where pip will install to
ENV PYROOT /pyroot
# A convenience to have console_scripts in PATH
ENV PYTHONUSERBASE $PYROOT

WORKDIR /build

# Install pipenv
RUN pip install 'pipenv==2018.11.26'

# Copy Pipfile, Pipfile.lock to the build container
COPY Pipfile* ./

# Install build dependencies
RUN apt-get update && \
  apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*
# Install dependencies
RUN PIP_USER=1 PIP_IGNORE_INSTALLED=1 pipenv install --system --deploy --ignore-pipfile

####################
# Production image #
####################
FROM python:3.8.7-slim

# Dependencies path
ENV PYROOT /pyroot
ENV PATH $PYROOT/bin:$PATH
ENV PYTHONPATH $PYROOT/lib/python:$PATH
# This is crucial for pkg_resources to work
ENV PYTHONUSERBASE $PYROOT

WORKDIR /src

# Copy dependencies from build container
COPY --from=builder $PYROOT/bin/ $PYROOT/bin/
COPY --from=builder $PYROOT/lib/ $PYROOT/lib/

# Copy source code
COPY . ./

# Start application
ENTRYPOINT ["python", "main.py"]
