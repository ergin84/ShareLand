FROM python:3.12-alpine

LABEL maintainer="Ergin Mehmeti <ergin.mehmeti@logos-ri.eu>"

ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python3","manage.py","runserver", "0.0.0.0:8080"]