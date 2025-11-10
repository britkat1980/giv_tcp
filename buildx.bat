docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-dev:3.5.1 -t britkat/giv_tcp-dev:latest --push .
::docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-beta:3.3.15 -t britkat/giv_tcp-beta:latest --push .
::docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-ma:latest -t britkat/giv_tcp-ma:3.5 --push .