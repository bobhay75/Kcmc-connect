FROM php@sha256:118ef4fb1db5e866fb604f2f260da81f819a0a1eac87a4083f9194f48e00beee
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /source
