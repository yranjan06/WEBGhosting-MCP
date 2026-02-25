FROM golang:1.22-bookworm

WORKDIR /app

# Install basic system requirements
RUN apt-get update && apt-get install -y \
    ca-certificates \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cache Go modules
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build the binary
COPY . .
RUN go build -o /app/webmcp cmd/server/main.go

# Install Playwright dependencies and the exact Chromium browser version requried by the module
RUN go run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps

# Expose the HTTP/SSE port if user wants to run in remote mode (optional)
EXPOSE 8080

# Default entrypoint runs the MCP Server in stdio mode, but users can override
ENTRYPOINT ["/app/webmcp"]
