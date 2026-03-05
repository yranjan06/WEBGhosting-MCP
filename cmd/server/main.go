package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	mcp_golang "github.com/metoro-io/mcp-golang"
	"github.com/metoro-io/mcp-golang/transport/stdio"
	"github.com/ranjanyadav/web-mcp/pkg/agent"
	"github.com/ranjanyadav/web-mcp/pkg/browser"
	"github.com/ranjanyadav/web-mcp/pkg/plugins"
	"github.com/ranjanyadav/web-mcp/pkg/transport/sse"
)

func main() {
	// ─── Flags ───
	cdpEndpoint := flag.String("connect-cdp", "", "WebSocket debugger URL to connect to an existing browser")
	port := flag.Int("port", 0, "Port for HTTP/SSE mode (default: 0 = stdio mode)")
	humanize := flag.Bool("humanize", true, "Enable human-like mouse movements, scrolling, and typing delays to bypass anti-bot detection")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "%s%sWEBGhosting%s v%s — AI-powered stealth browser for LLM agents\n\n", ColorBold, ColorCyan, ColorReset, Version)
		fmt.Fprintln(os.Stderr, "Usage:")
		fmt.Fprintln(os.Stderr, "  webmcp                          Start in stdio mode (for IDE integration)")
		fmt.Fprintln(os.Stderr, "  webmcp --port=8080              Start in HTTP/SSE mode")
		fmt.Fprintln(os.Stderr, "  webmcp --connect-cdp=ws://...   Connect to existing browser")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "Environment:")
		fmt.Fprintln(os.Stderr, "  AI_API_KEY      API key for LLM provider (required for AI click/type)")
		fmt.Fprintln(os.Stderr, "  AI_BASE_URL     Custom LLM endpoint (default: OpenAI)")
		fmt.Fprintln(os.Stderr, "  AI_MODEL        Model name (default: gpt-4o)")
		fmt.Fprintln(os.Stderr, "  OPENAI_API_KEY  Legacy alias for AI_API_KEY")
		fmt.Fprintln(os.Stderr, "  HTTP_PROXY      Proxy server (e.g., http://proxy.example.com:8080)")
		fmt.Fprintln(os.Stderr, "  PROXY_USERNAME  Username for proxy authentication")
		fmt.Fprintln(os.Stderr, "  PROXY_PASSWORD  Password for proxy authentication")
		fmt.Fprintln(os.Stderr, "  BROWSER_HEADLESS       Set to 'true' to hide browser window (background mode)")
		fmt.Fprintln(os.Stderr, "  BROWSER_USER_DATA_DIR  Path to save browser sessions/cookies across restarts")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "Flags:")
		flag.PrintDefaults()
	}

	flag.Parse()

	// ─── Logger Setup ───
	log.SetFlags(log.Ltime)
	log.SetPrefix(ColorDim + "[webghosting] " + ColorReset)

	// ─── Banner ───
	fmt.Fprintf(os.Stderr, "\n%s", ColorCyan)
	fmt.Fprintln(os.Stderr, `  __        _______ ____   ____  _               _   _             `)
	fmt.Fprintln(os.Stderr, `  \ \      / / ____| __ ) / ___|| |__   ___  ___| |_(_)_ __   __ _ `)
	fmt.Fprintln(os.Stderr, `   \ \ /\ / /|  _| |  _ \| |  _ | '_ \ / _ \/ __| __| | '_ \ / _`+"`"+` |`)
	fmt.Fprintln(os.Stderr, `    \ V  V / | |___| |_) | |_| || | | | (_) \__ \ |_| | | | | (_| |`)
	fmt.Fprintln(os.Stderr, `     \_/\_/  |_____|____/ \____||_| |_|\___/|___/\__|_|_| |_|\__, |`)
	fmt.Fprintln(os.Stderr, `                                                             |___/ `)
	fmt.Fprintf(os.Stderr, "%s\n", ColorReset)
	fmt.Fprintf(os.Stderr, "  %sType: Local Agentic Browser  │  Mode: Stealth  │  v%s%s\n", ColorDim, Version, ColorReset)
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintf(os.Stderr, "  %sQuick Start:%s\n", ColorBold, ColorReset)
	fmt.Fprintf(os.Stderr, "  %sAdd to your IDE's MCP config (settings.json or mcp.json):%s\n", ColorDim, ColorReset)
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintf(os.Stderr, "    %s{\"mcpServers\": {\"webghosting\": {\"command\": \"/path/to/webmcp\"}}}%s\n", ColorCyan, ColorReset)
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintf(os.Stderr, "  %sFor AI-driven click/type, set: export AI_API_KEY=sk-...%s\n", ColorDim, ColorReset)
	fmt.Fprintf(os.Stderr, "  %sCustom LLM: export AI_BASE_URL=http://localhost:11434/v1%s\n", ColorDim, ColorReset)
	fmt.Fprintf(os.Stderr, "  %sUse Proxy : export HTTP_PROXY=http://proxy...%s\n", ColorDim, ColorReset)
	fmt.Fprintf(os.Stderr, "  %sRun --help for all options%s\n\n", ColorDim, ColorReset)

	// ─── Initialize Components ───
	engine, err := browser.New(*cdpEndpoint)
	if err != nil {
		fmt.Fprintf(os.Stderr, "  %s✗ Browser engine failed to initialize%s\n", ColorRed, ColorReset)
		fmt.Fprintf(os.Stderr, "  %sRun: go run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps%s\n\n", ColorDim, ColorReset)
		os.Exit(1)
	}
	engine.Humanize = *humanize
	defer func() {
		engine.Close()
		fmt.Fprintf(os.Stderr, "\n  %s✓ Shutdown complete%s\n", ColorDim, ColorReset)
	}()

	aiAgent, err := agent.New()
	if err != nil {
		log.Printf("%s[AI]%s Agent not available: %v (AI-driven tools disabled)", ColorYellow, ColorReset, err)
	}

	stateStore := agent.NewStateStore()

	// ─── Choose Transport ───
	var server *mcp_golang.Server
	if *port > 0 {
		sseTransport := sse.NewSSEServerTransport("/messages", "/sse")
		server = mcp_golang.NewServer(sseTransport)
		http.Handle("/sse", sseTransport)
		http.Handle("/messages", sseTransport)
	} else {
		server = mcp_golang.NewServer(stdio.NewStdioServerTransport())
	}

	// ─── Register All Tools ───
	RegisterAllTools(server, engine, aiAgent, stateStore)

	// ─── Load Dynamic Plugins ───
	extDir := "./extensions"
	if err := plugins.LoadPlugins(server, engine, extDir); err != nil {
		log.Printf("%s[PLUGINS]%s Failed to load extensions: %v", ColorYellow, ColorReset, err)
	}

	// ─── Start Server ───
	if *port > 0 {
		go func() {
			if err := server.Serve(); err != nil {
				log.Printf("%sServer error: %v%s", ColorRed, err, ColorReset)
			}
		}()
		fmt.Fprintf(os.Stderr, "  %s→ Ready at http://localhost:%d%s  %sCtrl+C to stop%s\n\n", ColorGreen, *port, ColorReset, ColorDim, ColorReset)
		if err := http.ListenAndServe(fmt.Sprintf(":%d", *port), nil); err != nil {
			log.Fatalf("%sHTTP server failed: %v%s", ColorRed, err, ColorReset)
		}
	} else {
		fmt.Fprintf(os.Stderr, "  %s→ Listening on stdin%s  %s(waiting for MCP client)%s\n\n", ColorGreen, ColorReset, ColorDim, ColorReset)
		if err := server.Serve(); err != nil {
			log.Fatalf("%sServer error: %v%s", ColorRed, err, ColorReset)
		}
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan
		fmt.Fprintf(os.Stderr, "\n")
	}
}
