package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	mcp_golang "github.com/metoro-io/mcp-golang"
	"github.com/metoro-io/mcp-golang/transport/stdio"
	"github.com/playwright-community/playwright-go"
	"github.com/ranjanyadav/web-mcp/pkg/agent"
	"github.com/ranjanyadav/web-mcp/pkg/browser"
	"github.com/ranjanyadav/web-mcp/pkg/transport/sse"
)

type BrowseArgs struct {
	URL string `json:"url" jsonschema:"required,description=The URL to navigate to"`
}

type ClickArgs struct {
	Prompt string `json:"prompt" jsonschema:"required,description=Natural language description of the element to click"`
}

type TypeArgs struct {
	Prompt string `json:"prompt" jsonschema:"required,description=Natural language description of the element to type into"`
	Text   string `json:"text" jsonschema:"required,description=The text to type"`
}

type ExtractArgs struct {
	Schema string `json:"schema" jsonschema:"required,description=JSON schema or description of data to extract"`
}

const (
	Version = "2.0.0"

	ColorReset  = "\033[0m"
	ColorRed    = "\033[31m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
	ColorBlue   = "\033[34m"
	ColorCyan   = "\033[36m"
	ColorDim    = "\033[2m"
	ColorBold   = "\033[1m"
	SymCheck    = "✓"
	SymCross    = "✗"
	SymWarn     = "⚠"
	SymArrow    = "→"
)

func main() {
	// ─── Flags ───
	cdpEndpoint := flag.String("connect-cdp", "", "WebSocket debugger URL to connect to an existing browser")
	port := flag.Int("port", 0, "Port for HTTP/SSE mode (default: 0 = stdio mode)")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "%s%sGO-WebMcp%s v%s — AI-powered stealth browser for LLM agents\n\n", ColorBold, ColorCyan, ColorReset, Version)
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
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "Flags:")
		flag.PrintDefaults()
	}

	flag.Parse()

	// ─── Logger Setup ───
	log.SetFlags(log.Ltime)
	log.SetPrefix(ColorDim + "[webmcp] " + ColorReset)

	// ─── Banner ───
	fmt.Fprintf(os.Stderr, "\n%s", ColorCyan)
	fmt.Fprintln(os.Stderr, `   ______           _       __     __    __  ___  __________`)
	fmt.Fprintln(os.Stderr, `  / ____/___       | |     / /__  / /_  /  |/  / / ____/ __ \`)
	fmt.Fprintln(os.Stderr, ` / / __/ __ \______| | /| / / _ \/ __ \/ /|_/ / / /   / /_/ /`)
	fmt.Fprintln(os.Stderr, `/ /_/ / /_/ /_____/| |/ |/ /  __/ /_/ / /  / / / /___/ ____/`)
	fmt.Fprintln(os.Stderr, `\____/\____/       |__/|__/\___/_.___/_/  /_/  \____/_/`)
	fmt.Fprintf(os.Stderr, "%s\n", ColorReset)
	fmt.Fprintf(os.Stderr, "  %sType: Local Agentic Browser  │  Mode: Stealth  │  v%s%s\n", ColorDim, Version, ColorReset)
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintf(os.Stderr, "  %sQuick Start:%s\n", ColorBold, ColorReset)
	fmt.Fprintf(os.Stderr, "  %sAdd to your IDE's MCP config (settings.json or mcp.json):%s\n", ColorDim, ColorReset)
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintf(os.Stderr, "    %s{\"mcpServers\": {\"go-webmcp\": {\"command\": \"/path/to/webmcp\"}}}%s\n", ColorCyan, ColorReset)
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
	defer func() {
		engine.Close()
		fmt.Fprintf(os.Stderr, "\n  %s✓ Shutdown complete%s\n", ColorDim, ColorReset)
	}()

	aiAgent, err := agent.New()
	hasAI := err == nil
	_ = hasAI

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

	// Register tools (common for both)
	err = server.RegisterTool("browse", "Navigate to a URL with stealth mode enabled", func(args BrowseArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[BROWSE]%s Navigating to: %s", ColorBlue, ColorReset, args.URL)
		if err := engine.Navigate(args.URL); err != nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Failed to navigate: %v", err))), nil
		}
		log.Printf("%s[BROWSE]%s Success: Navigated to %s", ColorGreen, ColorReset, args.URL)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Successfully navigated to %s", args.URL))), nil
	})
	if err != nil {
		panic(err)
	}

	err = server.RegisterTool("click", "Click an element identified by a natural language prompt", func(args ClickArgs) (*mcp_golang.ToolResponse, error) {
		if aiAgent == nil {
			return nil, fmt.Errorf("AI agent not initialized")
		}
		log.Printf("%s[CLICK]%s Looking for element: '%s'", ColorBlue, ColorReset, args.Prompt)

		page, err := engine.Page()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}

		selector, err := aiAgent.FindElement(page, args.Prompt)
		if err != nil {
			return nil, fmt.Errorf("failed to find element: %w", err)
		}
		if err := engine.HumanClickElement(selector); err != nil {
			return nil, fmt.Errorf("failed to click selector '%s': %w", selector, err)
		}
		log.Printf("%s[CLICK]%s Success: Clicked '%s' (Selector: %s)", ColorGreen, ColorReset, args.Prompt, selector)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Clicked element '%s' (selector: %s)", args.Prompt, selector))), nil
	})
	if err != nil {
		panic(err)
	}

	err = server.RegisterTool("type", "Type text into an element identified by a natural language prompt", func(args TypeArgs) (*mcp_golang.ToolResponse, error) {
		if aiAgent == nil {
			return nil, fmt.Errorf("AI agent not initialized")
		}
		log.Printf("%s[TYPE]%s Looking for element: '%s' to type '%s'", ColorBlue, ColorReset, args.Prompt, args.Text)

		page, err := engine.Page()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}

		selector, err := aiAgent.FindElement(page, args.Prompt)
		if err != nil {
			return nil, fmt.Errorf("failed to find element: %w", err)
		}
		if err := engine.HumanType(selector, args.Text); err != nil {
			return nil, fmt.Errorf("failed to type into selector '%s': %w", selector, err)
		}
		log.Printf("%s[TYPE]%s Success: Typed into '%s'", ColorGreen, ColorReset, args.Prompt)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Typed '%s' into '%s'", args.Text, args.Prompt))), nil
	})
	if err != nil {
		panic(err)
	}

	err = server.RegisterTool("extract", "Extract page content as text or structured data based on a schema description", func(args ExtractArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[EXTRACT]%s Schema: %s", ColorBlue, ColorReset, args.Schema)
		page, err := engine.Page()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}
		title, _ := page.Title()
		url := page.URL()
		// Get page text content for extraction
		textContent, err := page.Locator("body").InnerText()
		if err != nil {
			textContent = "(could not extract text)"
		}
		// Truncate if too large
		if len(textContent) > 20000 {
			textContent = textContent[:20000] + "\n...(truncated)"
		}
		result := fmt.Sprintf("Page: %s\nURL: %s\nSchema requested: %s\n\nContent:\n%s", title, url, args.Schema, textContent)
		log.Printf("%s[EXTRACT]%s Success: Extracted %d chars", ColorGreen, ColorReset, len(textContent))
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(result)), nil
	})
	if err != nil {
		panic(err)
	}

	type WaitForSelectorArgs struct {
		Selector string `json:"selector" jsonschema:"required,description=CSS selector to wait for"`
		State    string `json:"state" jsonschema:"description=State to wait for (attached, detached, visible, hidden). Default: visible"`
	}

	err = server.RegisterTool("wait_for_selector", "Wait for an element to appear or change state", func(args WaitForSelectorArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[WAIT]%s Waiting for selector '%s' (State: %s)", ColorBlue, ColorReset, args.Selector, args.State)
		if err := engine.WaitForSelector(args.Selector, args.State); err != nil {
			return nil, fmt.Errorf("wait failed: %w", err)
		}
		log.Printf("%s[WAIT]%s Success: Selector '%s' is %s", ColorGreen, ColorReset, args.Selector, args.State)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Selector '%s' is now %s", args.Selector, args.State))), nil
	})
	if err != nil {
		panic(err)
	}

	type WaitForLoadStateArgs struct {
		State string `json:"state" jsonschema:"description=Load state to wait for (load, domcontentloaded, networkidle). Default: load"`
	}

	err = server.RegisterTool("wait_for_load_state", "Wait for navigation or network to settle", func(args WaitForLoadStateArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[WAIT]%s Waiting for load state: %s", ColorBlue, ColorReset, args.State)
		if err := engine.WaitForLoadState(args.State); err != nil {
			return nil, fmt.Errorf("wait failed: %w", err)
		}
		log.Printf("%s[WAIT]%s Success: Reached load state %s", ColorGreen, ColorReset, args.State)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Page reached load state: %s", args.State))), nil
	})
	if err != nil {
		panic(err)
	}

	type GetConsoleLogsArgs struct{}

	err = server.RegisterTool("get_console_logs", "Get browser console logs (errors, warnings, logs)", func(args GetConsoleLogsArgs) (*mcp_golang.ToolResponse, error) {
		logs := engine.GetConsoleLogs()
		log.Printf("%s[LOGS]%s Retrieved %d console messages", ColorBlue, ColorReset, len(logs))
		var content string
		if len(logs) == 0 {
			content = "No new console logs."
		} else {
			for _, l := range logs {
				content += l + "\n"
			}
		}
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(content)), nil
	})
	if err != nil {
		panic(err)
	}

	type ExecuteJSArgs struct {
		Script string `json:"script" jsonschema:"required,description=Javascript code to execute. Return value will be captured."`
	}

	err = server.RegisterTool("execute_js", "Execute Javascript on the page", func(args ExecuteJSArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[JS]%s Executing script...", ColorBlue, ColorReset)
		result, err := engine.ExecuteScript(args.Script)
		if err != nil {
			return nil, fmt.Errorf("script execution failed: %w", err)
		}
		log.Printf("%s[JS]%s Success. Result: %s", ColorGreen, ColorReset, result)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(result)), nil
	})
	if err != nil {
		panic(err)
	}

	type ConfigureDialogArgs struct {
		Action string `json:"action" jsonschema:"required,description=Action to take on future dialogs (accept or dismiss). Default: accept"`
	}

	err = server.RegisterTool("configure_dialog", "Set how to handle browser dialogs (alert, confirm, prompt)", func(args ConfigureDialogArgs) (*mcp_golang.ToolResponse, error) {
		if args.Action != "accept" && args.Action != "dismiss" {
			return nil, fmt.Errorf("invalid action '%s', must be 'accept' or 'dismiss'", args.Action)
		}
		engine.SetDialogAction(args.Action)
		log.Printf("%s[DIALOG]%s Configured to %s future dialogs", ColorBlue, ColorReset, args.Action)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Dialogs will now be %sed", args.Action))), nil
	})
	if err != nil {
		panic(err)
	}

	type PressKeyArgs struct {
		Key string `json:"key" jsonschema:"required,description=Key or combination to press (e.g., 'Enter', 'Control+A', 'Tab')"`
	}

	type ScrollArgs struct {
		Direction string `json:"direction" jsonschema:"required,description=Scroll direction: 'up' or 'down'"`
		Amount    int    `json:"amount" jsonschema:"required,description=Amount of pixels to scroll"`
	}

	err = server.RegisterTool("scroll", "Scroll the page up or down with natural human-like behavior", func(args ScrollArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[SCROLL]%s Direction: %s, Amount: %d", ColorBlue, ColorReset, args.Direction, args.Amount)
		if args.Direction != "up" && args.Direction != "down" {
			return nil, fmt.Errorf("invalid direction '%s', must be 'up' or 'down'", args.Direction)
		}
		if err := engine.HumanScrollPage(args.Direction, args.Amount); err != nil {
			return nil, fmt.Errorf("scroll failed: %w", err)
		}
		log.Printf("%s[SCROLL]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Scrolled %s by %d pixels", args.Direction, args.Amount))), nil
	})
	if err != nil {
		panic(err)
	}

	err = server.RegisterTool("press_key", "Simulate keyboard key press", func(args PressKeyArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[KEY]%s Pressing key: %s", ColorBlue, ColorReset, args.Key)
		if err := engine.PressKey(args.Key); err != nil {
			return nil, fmt.Errorf("key press failed: %w", err)
		}
		log.Printf("%s[KEY]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Pressed key: %s", args.Key))), nil
	})
	if err != nil {
		panic(err)
	}

	type GetAccessibilityTreeArgs struct{}

	err = server.RegisterTool("get_accessibility_tree", "Get the semantic accessibility tree of the page (works without AI agent)", func(args GetAccessibilityTreeArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[AX]%s Fetching accessibility tree...", ColorBlue, ColorReset)
		page, err := engine.Page()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}
		tree, err := page.Locator("body").AriaSnapshot()
		if err != nil {
			return nil, fmt.Errorf("failed to get accessibility tree: %w", err)
		}
		log.Printf("%s[AX]%s Success. Tree length: %d chars", ColorGreen, ColorReset, len(tree))
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(tree)), nil
	})
	if err != nil {
		panic(err)
	}

	// ─── Multi-tab Tools ───

	type OpenTabArgs struct{}

	err = server.RegisterTool("open_tab", "Open a new browser tab and switch to it", func(args OpenTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Opening new tab...", ColorBlue, ColorReset)
		idx, err := engine.OpenTab()
		if err != nil {
			return nil, fmt.Errorf("failed to open tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Opened tab %d", ColorGreen, ColorReset, idx)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Opened new tab (index: %d). Switched to it.", idx))), nil
	})
	if err != nil {
		panic(err)
	}

	type SwitchTabArgs struct {
		Index int `json:"index" jsonschema:"required,description=Tab index to switch to (0-based)"`
	}

	err = server.RegisterTool("switch_tab", "Switch to a different browser tab by index", func(args SwitchTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Switching to tab %d", ColorBlue, ColorReset, args.Index)
		if err := engine.SwitchTab(args.Index); err != nil {
			return nil, fmt.Errorf("failed to switch tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Now on tab %d", ColorGreen, ColorReset, args.Index)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Switched to tab %d", args.Index))), nil
	})
	if err != nil {
		panic(err)
	}

	type CloseTabArgs struct {
		Index int `json:"index" jsonschema:"required,description=Tab index to close (0-based)"`
	}

	err = server.RegisterTool("close_tab", "Close a browser tab by index", func(args CloseTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Closing tab %d", ColorBlue, ColorReset, args.Index)
		if err := engine.CloseTab(args.Index); err != nil {
			return nil, fmt.Errorf("failed to close tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Closed tab %d", ColorGreen, ColorReset, args.Index)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Closed tab %d", args.Index))), nil
	})
	if err != nil {
		panic(err)
	}

	type ListTabsArgs struct{}

	err = server.RegisterTool("list_tabs", "List all open browser tabs with their titles and URLs", func(args ListTabsArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Listing tabs", ColorBlue, ColorReset)
		tabs, err := engine.ListTabs()
		if err != nil {
			return nil, fmt.Errorf("failed to list tabs: %w", err)
		}
		tabJSON, _ := json.MarshalIndent(tabs, "", "  ")
		log.Printf("%s[TABS]%s Found %d tabs", ColorGreen, ColorReset, len(tabs))
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(tabJSON))), nil
	})
	if err != nil {
		panic(err)
	}

	// ─── Navigation History Tools ───

	type GoBackArgs struct{}

	err = server.RegisterTool("go_back", "Navigate the browser back to the previous page", func(args GoBackArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[NAV]%s Going back", ColorBlue, ColorReset)
		if err := engine.GoBack(); err != nil {
			return nil, fmt.Errorf("go back failed: %w", err)
		}
		page, err := engine.Page()
		if err != nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("Navigated back (could not read page info)")), nil
		}
		title, _ := page.Title()
		url := page.URL()
		log.Printf("%s[NAV]%s Success: Now at %s", ColorGreen, ColorReset, url)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Navigated back. Title: %s, URL: %s", title, url))), nil
	})
	if err != nil {
		panic(err)
	}

	type GoForwardArgs struct{}

	err = server.RegisterTool("go_forward", "Navigate the browser forward to the next page", func(args GoForwardArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[NAV]%s Going forward", ColorBlue, ColorReset)
		if err := engine.GoForward(); err != nil {
			return nil, fmt.Errorf("go forward failed: %w", err)
		}
		page, err := engine.Page()
		if err != nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("Navigated forward (could not read page info)")), nil
		}
		title, _ := page.Title()
		url := page.URL()
		log.Printf("%s[NAV]%s Success: Now at %s", ColorGreen, ColorReset, url)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Navigated forward. Title: %s, URL: %s", title, url))), nil
	})
	if err != nil {
		panic(err)
	}

	// ─── Network Monitoring Tools ───

	type GetNetworkRequestsArgs struct{}

	err = server.RegisterTool("get_network_requests", "Get all HTTP requests made by the current page", func(args GetNetworkRequestsArgs) (*mcp_golang.ToolResponse, error) {
		reqs := engine.GetNetworkRequests()
		log.Printf("%s[NET]%s Retrieved %d network requests", ColorBlue, ColorReset, len(reqs))
		reqJSON, _ := json.MarshalIndent(reqs, "", "  ")
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(reqJSON))), nil
	})
	if err != nil {
		panic(err)
	}

	type ClearNetworkRequestsArgs struct{}

	err = server.RegisterTool("clear_network_requests", "Clear the captured network request log", func(args ClearNetworkRequestsArgs) (*mcp_golang.ToolResponse, error) {
		engine.ClearNetworkRequests()
		log.Printf("%s[NET]%s Cleared network requests", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("Network request log cleared")), nil
	})
	if err != nil {
		panic(err)
	}

	// ─── Batch Form Fill Tool ───

	type FormField struct {
		Selector string `json:"selector" jsonschema:"required,description=CSS selector of the input element"`
		Value    string `json:"value" jsonschema:"required,description=Value to fill in"`
		Type     string `json:"type" jsonschema:"description=Field type: textbox (default) or checkbox or select"`
	}
	type FillFormArgs struct {
		Fields []FormField `json:"fields" jsonschema:"required,description=Array of form fields to fill"`
	}

	err = server.RegisterTool("fill_form", "Fill multiple form fields in one call with human-like delays", func(args FillFormArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[FORM]%s Filling %d fields", ColorBlue, ColorReset, len(args.Fields))
		var results []string
		for _, field := range args.Fields {
			fieldType := field.Type
			if fieldType == "" {
				fieldType = "textbox"
			}
			switch fieldType {
			case "textbox":
				if err := engine.HumanType(field.Selector, field.Value); err != nil {
					results = append(results, fmt.Sprintf("FAIL %s: %v", field.Selector, err))
					continue
				}
				results = append(results, fmt.Sprintf("OK filled '%s' into %s", field.Value, field.Selector))
			case "checkbox":
				page, err := engine.Page()
				if err != nil {
					results = append(results, fmt.Sprintf("FAIL %s: %v", field.Selector, err))
					continue
				}
				checked := field.Value == "true"
				if err := page.Locator(field.Selector).SetChecked(checked); err != nil {
					results = append(results, fmt.Sprintf("FAIL %s: %v", field.Selector, err))
					continue
				}
				results = append(results, fmt.Sprintf("OK set %s to %v", field.Selector, checked))
			case "select":
				page, err := engine.Page()
				if err != nil {
					results = append(results, fmt.Sprintf("FAIL %s: %v", field.Selector, err))
					continue
				}
				if _, err := page.Locator(field.Selector).SelectOption(playwright.SelectOptionValues{Labels: &[]string{field.Value}}); err != nil {
					results = append(results, fmt.Sprintf("FAIL %s: %v", field.Selector, err))
					continue
				}
				results = append(results, fmt.Sprintf("OK selected '%s' in %s", field.Value, field.Selector))
			default:
				results = append(results, fmt.Sprintf("SKIP %s: unknown type '%s'", field.Selector, fieldType))
			}
		}
		log.Printf("%s[FORM]%s Done: %d fields processed", ColorGreen, ColorReset, len(args.Fields))
		content := "Form fill results:\n"
		for _, r := range results {
			content += "- " + r + "\n"
		}
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(content)), nil
	})
	if err != nil {
		panic(err)
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
