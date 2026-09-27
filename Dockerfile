# `graduate up --demo` in a container (#58): docker build -t graduate . && docker run --rm -p 4141:4141 graduate
FROM python:3.12-slim
WORKDIR /src
COPY pyproject.toml ./
COPY graduate graduate
COPY ui ui
COPY fixtures fixtures
RUN pip install --no-cache-dir . && rm -rf /src
WORKDIR /
ENV GRADUATE_HOST=0.0.0.0
EXPOSE 4141
CMD ["graduate", "up", "--demo"]
