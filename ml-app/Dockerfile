FROM python:3.12-slim

WORKDIR /service

ENV PIPENV_VENV_IN_PROJECT=1

RUN pip install --no-cache-dir pipenv

COPY Pipfile Pipfile.lock* ./
RUN pipenv install --deploy

COPY ml-app/ ./app/

EXPOSE 8000

CMD ["pipenv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
