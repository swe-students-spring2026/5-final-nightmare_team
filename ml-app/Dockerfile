FROM python:3.12-slim

WORKDIR /service

ENV PIPENV_VENV_IN_PROJECT=1

RUN pip install --no-cache-dir pipenv

COPY ml-app/Pipfile ml-app/Pipfile.lock* ./
RUN pipenv install --deploy

COPY ml-app/ ./app/

EXPOSE 8000

CMD ["pipenv", "run", "python", "-m", "app.main"]
