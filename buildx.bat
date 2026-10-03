 docker run --privileged --rm tonistiigi/binfmt --install all
docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-dev:3.6.0.8 -t britkat/giv_tcp-dev:latest --push .
docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-beta:3.6.0-beta5 -t britkat/giv_tcp-beta:latest --push .
::docker buildx build --platform linux/amd64,linux/arm64 -t britkat/giv_tcp-ma:latest -t britkat/giv_tcp-ma:3.5 --push .