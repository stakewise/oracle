from pathlib import Path

from sys import path

# https://github.com/protocolbuffers/protobuf/issues/1491
path.append(str(Path(__file__).parent))
