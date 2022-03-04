# Typically we wouldn't grab the latest from an external repo. We would
# lock to some version that is stored in our local docker registry.
FROM node:current-alpine3.15

# Expose the port we are using
EXPOSE 9997/tcp

# Set the Working Directory
WORKDIR /app

# Copy over the App code
COPY src/app /app
