FROM python:3.9-alpine3.15

# Install system dependencies
RUN apk add --update --no-cache \
        build-base \
        gettext \
        git \
        jpeg-dev \
        libffi-dev \
        libxml2-dev \
        libxslt-dev \
        openssh \
        postgresql-client \
        postgresql-dev \
        python3-dev \
        zlib-dev \
        lcms2-dev \
        curl-dev \
        curl
ENV LIBRARY_PATH=/lib:/usr/lib
ENV POETRY_VERSION=1.2.0

# Instruct pip to install editable dependencies in a specific path, because
# otherwise pip would install them in `/app/src` and they would disappear in
# the local development environment where we mount over `/app/src` with the
# source code from the host.
RUN mkdir /deps
ENV PIP_SRC /deps
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=false
ENV PIP_NO_COMPILE=no

# Create the directory for the application code
RUN mkdir /app
WORKDIR /app

# Install requirements
RUN pip install --upgrade pip

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
COPY poetry.lock pyproject.toml ./

RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# Install cloudflared
RUN curl -L --output cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && \
        chmod +x cloudflared && \
        mv cloudflared /usr/bin/
COPY docker/entrypoints/cloudflare-tunnel.sh /usr/bin/cloudflare-tunnel
RUN curl --output /etc/ssl/certs/cloudflare.crt https://amuse.cloudflareaccess.com/cdn-cgi/access/certs

# Set poetry config
RUN poetry config virtualenvs.create false
RUN poetry config experimental.new-installer false
# Install packages
RUN --mount=type=ssh poetry install --no-interaction -v && find / | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf

# Add the source code
COPY src src
COPY Makefile setup.cfg ./
WORKDIR /app/src

# Add .git folder because it's need for codecov
COPY .git /app/src/git

# Add run-tests.sh file
COPY .circleci/scripts/run-tests.sh .

ENV DJANGO_SETTINGS_MODULE amuse.settings.unified
RUN DJANGO_SECRET_KEY=fake python3 manage.py collectstatic --noinput

CMD ["python3", "manage.py"]
