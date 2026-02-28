.PHONY: build install-deps run docker docker-compose clean help

# ─── Variables ───
BINARY   := webmcp
SRC      := cmd/server/*.go
GO       := go

# ─── Default ───
help: ## Show this help message
	@echo ""
	@echo "  Go-WebMCP — Intelligent Stealth Browser MCP Server"
	@echo ""
	@echo "  Usage:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Build ───
build: ## Compile the Go binary
	$(GO) build -o $(BINARY) $(SRC)
	@echo "✓ Built ./$(BINARY)"

# ─── Dependencies ───
install-deps: ## Install Playwright browsers & system deps
	$(GO) run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps
	@echo "✓ Playwright dependencies installed"

# ─── Run ───
run: build ## Build and run in stdio mode
	./$(BINARY)

run-sse: build ## Build and run in HTTP/SSE mode on port 8080
	./$(BINARY) --port=8080

# ─── Docker ───
docker: ## Build Docker image
	docker build -t go-webmcp .
	@echo "✓ Docker image built: go-webmcp"

docker-compose: ## Start with docker-compose
	docker-compose up --build

# ─── Clean ───
clean: ## Remove compiled binaries
	rm -f $(BINARY) server probe_sse
	@echo "✓ Cleaned"

# ─── Lint (future) ───
lint: ## Run golangci-lint (requires: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest)
	golangci-lint run ./...
