FROM python:3.7.4

# TODO: delete cache
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    npm \
    nodejs \
  && rm -rf /var/lib/apt/lists/*

ENV PIP_DISABLE_PIP_VERSION_CHECK=on

RUN pip install poetry wheel

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-dev

RUN npm install npm@latest -g

COPY package.json package-lock.json /app/
RUN npm install

COPY postcss.config.js tailwind.config.js webpack.config.js /app/
COPY src /app/src

COPY whatson /app/whatson
COPY elm.json /app/
RUN npm run prod

EXPOSE 5000
CMD ["gunicorn", "--bind", "5000", "--workers", "4", "whatson.wsgi:app"]
