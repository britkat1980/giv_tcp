::docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-dev:3.0.53 -t britkat/giv_tcp-dev:latest --push .
::docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-beta:3.1.3 -t britkat/giv_tcp-beta:latest --push .
docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-ma:latest -t britkat/giv_tcp-ma:3.1.3 --push .