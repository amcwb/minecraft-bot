FROM python:3.8-slim-buster
WORKDIR /
RUN pip3 install -r requirements.txt

COPY . .
CMD [ "python3", "src"]
