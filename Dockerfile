FROM python:3.9.6-slim
COPY . /Twiiiter/
WORKDIR /Twiiiter
RUN pip3 install poetry==1.1.7
RUN poetry install
EXPOSE 80
CMD [ "poetry", "run", "gunicorn", "--workers", "4", "twitter.cli:app", "--bind", "0.0.0.0:80" ]