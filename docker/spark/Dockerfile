FROM apache/spark:4.2.1-scala2.13-java17-python3-ubuntu

# Install the PostgreSQL adapter version pinned in the project's uv.lock.
USER root
RUN python3 -m pip install --no-cache-dir --only-binary=:all: \
    --target /opt/spark/python-deps \
    "psycopg[binary]==3.3.6"

# Make the adapter available to Python and run Spark as its regular user.
ENV PYTHONPATH=/opt/spark/python-deps
USER spark
