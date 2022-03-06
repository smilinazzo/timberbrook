ARG node_version=current

# Typically we wouldn't grab the latest from an external repo. We would
# lock to some version that is stored in our local docker registry.
FROM node:$node_version-alpine3.15

# Set the Working Directory
WORKDIR /app

# Copy over the App code
COPY src/app /app
