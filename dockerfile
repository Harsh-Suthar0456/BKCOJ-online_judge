FROM gcc:latest
RUN useradd -ms /bin/bash runner
USER runner

WORKDIR /home/runner
