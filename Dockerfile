FROM quay.io/devfile/universal-developer-image:ubi9-latest

USER 0

RUN alternatives --set python3 /usr/bin/python3.11 2>/dev/null || \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3

RUN pip install --no-cache-dir fastmcp httpx pyyaml

RUN dnf install -y bzip2 && dnf clean all && \
    curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash && \
    cp /home/user/.local/bin/goose /usr/local/bin/goose

RUN mkdir -p /home/user/.config/goose \
             /home/user/.local/share/goose \
             /home/user/.local/state/goose/logs/cli && \
    chmod -R 777 /home/user/.config /home/user/.local

RUN goose --version

RUN mkdir -p /opt/extensions && \
    curl -fSL -o /opt/extensions/vscode-goose.vsix \
    https://github.com/block/vscode-goose/releases/download/v0.2.1/vscode-goose-v0.2.1.vsix

USER 10001
