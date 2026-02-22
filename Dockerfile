# Build Stage
FROM golang:1.22-bookworm AS builder

WORKDIR /app

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build binary
RUN go build -o webmcp ./cmd/server

# Runtime Stage
FROM mcr.microsoft.com/playwright:v1.49.0-jammy

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/webmcp .

# Expose HTTP port for SSE mode
EXPOSE 8080

# Run
ENTRYPOINT ["./webmcp"]
CMD ["--port=8080"]
