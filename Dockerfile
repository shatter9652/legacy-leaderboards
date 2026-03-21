FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY . /app/

ARG SECRET_KEY
ENV SECRET_KEY=$SECRET_KEY

ARG DEBUG
ENV DEBUG=$DEBUG

ARG ALLOWED_HOSTS
ENV ALLOWED_HOSTS=$ALLOWED_HOSTS

RUN pip install uv

RUN uv pip install --system --no-cache-dir -r requirements.txt

RUN python manage.py collectstatic -v 3 --noinput

RUN python manage.py migrate --noinput

EXPOSE 8000

CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]
