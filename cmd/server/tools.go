package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"

	mcp_golang "github.com/metoro-io/mcp-golang"
	"github.com/playwright-community/playwright-go"
	"github.com/ranjanyadav/web-mcp/pkg/agent"
	"github.com/ranjanyadav/web-mcp/pkg/browser"
)

// ─── Arg Structs for MCP Tool Schemas ───

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
	Schema        interface{} `json:"schema" jsonschema:"required,description=JSON schema or description of data to extract"`
	ModelOverride string      `json:"model_override,omitempty" jsonschema:"description=Optional model to use for extraction instead of the default agent model (e.g. gpt-4o)"`
}

type ParallelExtractArgs struct {
	Urls          []string    `json:"urls" jsonschema:"required,description=Array of URLs to navigate and extract from in parallel"`
	Schema        interface{} `json:"schema" jsonschema:"required,description=JSON schema or description of data to extract"`
	ModelOverride string      `json:"model_override,omitempty" jsonschema:"description=Optional model to use for extraction instead of the default agent model (e.g. gpt-4o)"`
}

type WaitForSelectorArgs struct {
	Selector string `json:"selector" jsonschema:"required,description=CSS selector to wait for"`
	State    string `json:"state" jsonschema:"description=State to wait for (attached, detached, visible, hidden). Default: visible"`
}

type WaitForLoadStateArgs struct {
	State string `json:"state" jsonschema:"description=Load state to wait for (load, domcontentloaded, networkidle). Default: load"`
}

type GetConsoleLogsArgs struct{}

type ExecuteJSArgs struct {
	Script string `json:"script" jsonschema:"required,description=Javascript code to execute. Return value will be captured."`
}

type ConfigureDialogArgs struct {
	Action string `json:"action" jsonschema:"required,description=Action to take on future dialogs (accept or dismiss). Default: accept"`
}

type PressKeyArgs struct {
	Key string `json:"key" jsonschema:"required,description=Key or combination to press (e.g., 'Enter', 'Control+A', 'Tab')"`
}

type ScrollArgs struct {
	Direction string `json:"direction" jsonschema:"required,description=Scroll direction: 'up' or 'down'"`
	Amount    int    `json:"amount" jsonschema:"required,description=Amount of pixels to scroll"`
}

type GetAccessibilityTreeArgs struct{}

type CaptureLabeledSnapshotArgs struct{}
type CatchLabelSnapshotArgs struct{} // kept for placeholder

type MemorizeDataArgs struct {
	Key   string      `json:"key" jsonschema:"required,description=The unique key to store the data under"`
	Value interface{} `json:"value" jsonschema:"required,description=The value or JSON object to store"`
}

type RecallDataArgs struct {
	Key string `json:"key" jsonschema:"required,description=The unique key to retrieve the data for"`
}

type ListMemoryKeysArgs struct{}

type ScrollToBottomArgs struct{}

type OpenTabArgs struct{}

type SwitchTabArgs struct {
	Index int `json:"index" jsonschema:"required,description=Tab index to switch to (0-based)"`
}

type CloseTabArgs struct {
	Index int `json:"index" jsonschema:"required,description=Tab index to close (0-based)"`
}

type ListTabsArgs struct{}

type GetStatusArgs struct{}

type GoBackArgs struct{}

type GoForwardArgs struct{}

type GetNetworkRequestsArgs struct{}

type ClearNetworkRequestsArgs struct{}

type ScreenshotArgs struct{}

type FormField struct {
	Selector string `json:"selector" jsonschema:"required,description=CSS selector of the input element"`
	Value    string `json:"value" jsonschema:"required,description=Value to fill in"`
	Type     string `json:"type" jsonschema:"description=Field type: textbox (default) or checkbox or select"`
}

type FillFormArgs struct {
	Fields []FormField `json:"fields" jsonschema:"required,description=Array of form fields to fill"`
}

// ─── Tool Registration ───

// RegisterAllTools registers every MCP tool handler on the given server.
func RegisterAllTools(server *mcp_golang.Server, engine *browser.Engine, aiAgent *agent.Agent, stateStore *agent.StateStore) {

	// ─── browse ───
	must(server.RegisterTool("browse", "Navigate to a URL with stealth mode enabled", func(args BrowseArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[BROWSE]%s Navigating to: %s", ColorBlue, ColorReset, args.URL)
		engine.SetLastAction("browse: " + args.URL)
		if err := engine.Navigate(args.URL); err != nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Failed to navigate: %v", err))), nil
		}
		log.Printf("%s[BROWSE]%s Success: Navigated to %s", ColorGreen, ColorReset, args.URL)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Successfully navigated to %s", args.URL))), nil
	}))

	// ─── click ───
	must(server.RegisterTool("click", "Click an element identified by a natural language prompt", func(args ClickArgs) (*mcp_golang.ToolResponse, error) {
		// Smart Fallback: If prompt is actually a URL, just bypass AI and browse to it directly!
		if strings.HasPrefix(strings.ToLower(args.Prompt), "http://") || strings.HasPrefix(strings.ToLower(args.Prompt), "https://") {
			log.Printf("%s[CLICK]%s Prompt is a URL '%s'. Falling back to direct navigation.", ColorBlue, ColorReset, args.Prompt)
			if err := engine.Navigate(args.Prompt); err != nil {
				return nil, fmt.Errorf("failed to navigate to URL %s: %w", args.Prompt, err)
			}
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Navigated to %s directly instead of clicking.", args.Prompt))), nil
		}

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
	}))

	// ─── type ───
	must(server.RegisterTool("type", "Type text into an element identified by a natural language prompt", func(args TypeArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	// ─── extract ───
	must(server.RegisterTool("extract", "Extract page content as text or structured data based on a schema description", func(args ExtractArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[EXTRACT]%s Schema provided", ColorBlue, ColorReset)

		if aiAgent == nil {
			return nil, fmt.Errorf("AI agent is not initialized (missing API key?)")
		}

		page, err := engine.Page()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}

		extractedJson, err := aiAgent.ExtractData(page, args.Schema, args.ModelOverride)
		if err != nil {
			return nil, fmt.Errorf("extraction failed: %w", err)
		}

		log.Printf("%s[EXTRACT]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(extractedJson)), nil
	}))

	// ─── parallel_extract ───
	must(server.RegisterTool("parallel_extract", "Extract data from multiple URLs simultaneously in isolated sub-agents (parallel execution). Pass an array of URLs and a single schema.", func(args ParallelExtractArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[PARALLEL]%s Starting bulk extraction for %d URLs", ColorBlue, ColorReset, len(args.Urls))

		if aiAgent == nil {
			return nil, fmt.Errorf("AI agent is not initialized (missing API key?)")
		}

		pw, browser, err := engine.GetBrowserInstances()
		if err != nil {
			return nil, fmt.Errorf("browser not ready: %w", err)
		}

		results, err := aiAgent.ParallelExtract(pw, browser, args.Urls, args.Schema, args.ModelOverride)
		if err != nil {
			return nil, fmt.Errorf("parallel extraction failed: %w", err)
		}

		extractedJson, err := json.MarshalIndent(results, "", "  ")
		if err != nil {
			return nil, fmt.Errorf("failed to encode parallel results: %w", err)
		}

		log.Printf("%s[PARALLEL]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(extractedJson))), nil
	}))

	// ─── wait_for_selector ───
	must(server.RegisterTool("wait_for_selector", "Wait for an element to appear or change state", func(args WaitForSelectorArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[WAIT]%s Waiting for selector '%s' (State: %s)", ColorBlue, ColorReset, args.Selector, args.State)
		if err := engine.WaitForSelector(args.Selector, args.State); err != nil {
			return nil, fmt.Errorf("wait failed: %w", err)
		}
		log.Printf("%s[WAIT]%s Success: Selector '%s' is %s", ColorGreen, ColorReset, args.Selector, args.State)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Selector '%s' is now %s", args.Selector, args.State))), nil
	}))

	// ─── wait_for_load_state ───
	must(server.RegisterTool("wait_for_load_state", "Wait for navigation or network to settle", func(args WaitForLoadStateArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[WAIT]%s Waiting for load state: %s", ColorBlue, ColorReset, args.State)
		if err := engine.WaitForLoadState(args.State); err != nil {
			return nil, fmt.Errorf("wait failed: %w", err)
		}
		log.Printf("%s[WAIT]%s Success: Reached load state %s", ColorGreen, ColorReset, args.State)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Page reached load state: %s", args.State))), nil
	}))

	// ─── get_console_logs ───
	must(server.RegisterTool("get_console_logs", "Get browser console logs (errors, warnings, logs)", func(args GetConsoleLogsArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	// ─── execute_js ───
	must(server.RegisterTool("execute_js", "Execute Javascript on the page", func(args ExecuteJSArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[JS]%s Executing script...", ColorBlue, ColorReset)
		engine.SetLastAction("execute_js")
		result, err := engine.ExecuteScript(args.Script)
		if err != nil {
			return nil, fmt.Errorf("script execution failed: %w", err)
		}
		log.Printf("%s[JS]%s Success. Result: %s", ColorGreen, ColorReset, result)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(result)), nil
	}))

	// ─── configure_dialog ───
	must(server.RegisterTool("configure_dialog", "Set how to handle browser dialogs (alert, confirm, prompt)", func(args ConfigureDialogArgs) (*mcp_golang.ToolResponse, error) {
		if args.Action != "accept" && args.Action != "dismiss" {
			return nil, fmt.Errorf("invalid action '%s', must be 'accept' or 'dismiss'", args.Action)
		}
		engine.SetDialogAction(args.Action)
		log.Printf("%s[DIALOG]%s Configured to %s future dialogs", ColorBlue, ColorReset, args.Action)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Dialogs will now be %sed", args.Action))), nil
	}))

	// ─── scroll ───
	must(server.RegisterTool("scroll", "Scroll the page up or down with natural human-like behavior", func(args ScrollArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[SCROLL]%s Direction: %s, Amount: %d", ColorBlue, ColorReset, args.Direction, args.Amount)
		if args.Direction != "up" && args.Direction != "down" {
			return nil, fmt.Errorf("invalid direction '%s', must be 'up' or 'down'", args.Direction)
		}
		if err := engine.HumanScrollPage(args.Direction, args.Amount); err != nil {
			return nil, fmt.Errorf("scroll failed: %w", err)
		}
		log.Printf("%s[SCROLL]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Scrolled %s by %d pixels", args.Direction, args.Amount))), nil
	}))

	// ─── scroll_to_bottom ───
	must(server.RegisterTool("scroll_to_bottom", "Dynamically scroll the page to the bottom, automatically waiting for new content to load if it's an infinite feed", func(args ScrollToBottomArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[SCROLL]%s Scrolling continuously to bottom", ColorBlue, ColorReset)
		if err := engine.ScrollToBottom(); err != nil {
			return nil, fmt.Errorf("adaptive scroll failed: %w", err)
		}
		log.Printf("%s[SCROLL]%s Success (reached true bottom)", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("Successfully reached the bottom of the page.")), nil
	}))

	// ─── press_key ───
	must(server.RegisterTool("press_key", "Simulate keyboard key press", func(args PressKeyArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[KEY]%s Pressing key: %s", ColorBlue, ColorReset, args.Key)
		if err := engine.PressKey(args.Key); err != nil {
			return nil, fmt.Errorf("key press failed: %w", err)
		}
		log.Printf("%s[KEY]%s Success", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Pressed key: %s", args.Key))), nil
	}))

	// ─── get_accessibility_tree ───
	must(server.RegisterTool("get_accessibility_tree", "Get the semantic accessibility tree of the page (works without AI agent)", func(args GetAccessibilityTreeArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	// ─── capture_labeled_snapshot ───
	must(server.RegisterTool("capture_labeled_snapshot", "Take a screenshot of the page with interactive elements labeled (e.g., [e1], [e2]) for Vision-Language Models. Returns the base64 image and a map of labels to DOM selectors.", func(args CaptureLabeledSnapshotArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[VISION]%s Capturing labeled screenshot...", ColorBlue, ColorReset)
		base64Img, labelMap, err := engine.GetLabeledScreenshot()
		if err != nil {
			return nil, fmt.Errorf("failed to capture labeled screenshot: %w", err)
		}

		mapJSON, _ := json.MarshalIndent(labelMap, "", "  ")
		log.Printf("%s[VISION]%s Captured screenshot with %d labeled elements", ColorGreen, ColorReset, len(labelMap))

		content := fmt.Sprintf("```json\n%s\n```\n\nImage Base64 (JPEG):\n%s", string(mapJSON), base64Img)

		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(content)), nil
	}))

	// ─── Internal Memory Tools ───

	must(server.RegisterTool("memorize_data", "Store intermediate data (like JSON or strings) into the server's internal memory. Useful for saving outputs between steps.", func(args MemorizeDataArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[MEMORY]%s Storing data for key: '%s'", ColorBlue, ColorReset, args.Key)
		stateStore.Store(args.Key, args.Value)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Successfully stored data under key '%s'", args.Key))), nil
	}))

	must(server.RegisterTool("recall_data", "Retrieve previously stored data from the server's internal memory by key.", func(args RecallDataArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[MEMORY]%s Recalling data for key: '%s'", ColorBlue, ColorReset, args.Key)
		val := stateStore.Retrieve(args.Key)
		if val == nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("No data found for key '%s'", args.Key))), nil
		}
		
		valJSON, err := json.MarshalIndent(val, "", "  ")
		if err != nil {
			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("%v", val))), nil
		}
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(valJSON))), nil
	}))

	must(server.RegisterTool("list_memory_keys", "List all active keys currently stored in the internal memory.", func(args ListMemoryKeysArgs) (*mcp_golang.ToolResponse, error) {
		keys := stateStore.ListKeys()
		keysStr := strings.Join(keys, ", ")
		if len(keys) == 0 {
			keysStr = "(empty)"
		}
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Active memory keys: %s", keysStr))), nil
	}))

	// ─── Multi-tab Tools ───

	must(server.RegisterTool("open_tab", "Open a new browser tab and switch to it", func(args OpenTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Opening new tab...", ColorBlue, ColorReset)
		engine.SetLastAction("open_tab")
		idx, err := engine.OpenTab()
		if err != nil {
			return nil, fmt.Errorf("failed to open tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Opened tab %d", ColorGreen, ColorReset, idx)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Opened new tab (index: %d). Switched to it.", idx))), nil
	}))

	must(server.RegisterTool("switch_tab", "Switch to a different browser tab by index", func(args SwitchTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Switching to tab %d", ColorBlue, ColorReset, args.Index)
		if err := engine.SwitchTab(args.Index); err != nil {
			return nil, fmt.Errorf("failed to switch tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Now on tab %d", ColorGreen, ColorReset, args.Index)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Switched to tab %d", args.Index))), nil
	}))

	must(server.RegisterTool("close_tab", "Close a browser tab by index", func(args CloseTabArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Closing tab %d", ColorBlue, ColorReset, args.Index)
		if err := engine.CloseTab(args.Index); err != nil {
			return nil, fmt.Errorf("failed to close tab: %w", err)
		}
		log.Printf("%s[TABS]%s Success: Closed tab %d", ColorGreen, ColorReset, args.Index)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Closed tab %d", args.Index))), nil
	}))

	must(server.RegisterTool("list_tabs", "List all open browser tabs with their titles and URLs", func(args ListTabsArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[TABS]%s Listing tabs", ColorBlue, ColorReset)
		tabs, err := engine.ListTabs()
		if err != nil {
			return nil, fmt.Errorf("failed to list tabs: %w", err)
		}
		tabJSON, _ := json.MarshalIndent(tabs, "", "  ")
		log.Printf("%s[TABS]%s Found %d tabs", ColorGreen, ColorReset, len(tabs))
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(tabJSON))), nil
	}))

	// ─── Status Tool ───

	must(server.RegisterTool("get_status", "Get current browser status: initialized state, active tab URL/title, tab count and last action. Use this to check if the server is alive and what it last did.", func(args GetStatusArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[STATUS]%s Fetching browser status...", ColorBlue, ColorReset)
		status := engine.GetStatus()
		statusJSON, _ := json.MarshalIndent(status, "", "  ")
		log.Printf("%s[STATUS]%s OK — Last: %s (%ds ago)", ColorGreen, ColorReset, status.LastAction, status.SecondsSince)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(statusJSON))), nil
	}))

	// ─── Navigation History Tools ───

	must(server.RegisterTool("go_back", "Navigate the browser back to the previous page", func(args GoBackArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	must(server.RegisterTool("go_forward", "Navigate the browser forward to the next page", func(args GoForwardArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	// ─── Network Monitoring Tools ───

	must(server.RegisterTool("get_network_requests", "Get all HTTP requests made by the current page", func(args GetNetworkRequestsArgs) (*mcp_golang.ToolResponse, error) {
		reqs := engine.GetNetworkRequests()
		log.Printf("%s[NET]%s Retrieved %d network requests", ColorBlue, ColorReset, len(reqs))
		reqJSON, _ := json.MarshalIndent(reqs, "", "  ")
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(reqJSON))), nil
	}))

	must(server.RegisterTool("clear_network_requests", "Clear the captured network request log", func(args ClearNetworkRequestsArgs) (*mcp_golang.ToolResponse, error) {
		engine.ClearNetworkRequests()
		log.Printf("%s[NET]%s Cleared network requests", ColorGreen, ColorReset)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("Network request log cleared")), nil
	}))

	// ─── Batch Form Fill Tool ───

	must(server.RegisterTool("fill_form", "Fill multiple form fields in one call with human-like delays", func(args FillFormArgs) (*mcp_golang.ToolResponse, error) {
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
	}))

	// ─── Page Context ───
	must(server.RegisterTool("get_page_context", "Analyze the current page and return structured context: page type (search_results, product_page, login_page, article, form_page, listing_page, etc), interactive element counts, detected features (has_search, has_login, has_reviews, has_pagination, has_cart, has_video), main headings, and a brief text summary. This is a zero-cost instant analysis (no LLM used) — call it after every navigation to plan your next action intelligently.", func(args GetStatusArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[CONTEXT]%s Analyzing page...", ColorBlue, ColorReset)
		ctx, err := engine.GetPageContext()
		if err != nil {
			return nil, fmt.Errorf("page context failed: %v", err)
		}
		engine.SetLastAction("get_page_context")
		ctxJSON, _ := json.MarshalIndent(ctx, "", "  ")
		log.Printf("%s[CONTEXT]%s Page type: %s | %d links | reviews:%v | search:%v", ColorGreen, ColorReset, ctx.PageType, ctx.LinkCount, ctx.HasReviews, ctx.HasSearch)
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(string(ctxJSON))), nil
	}))

	// ─── Screenshot ───
	must(server.RegisterTool("screenshot", "Capture the current page viewport as base64 PNG. Useful for visual debugging and validation.", func(args ScreenshotArgs) (*mcp_golang.ToolResponse, error) {
		log.Printf("%s[SCREENSHOT]%s Capturing viewport...", ColorBlue, ColorReset)
		data, err := engine.Screenshot()
		if err != nil {
			return nil, fmt.Errorf("screenshot failed: %v", err)
		}
		engine.SetLastAction("screenshot")
		log.Printf("%s[SCREENSHOT]%s Captured (%d bytes base64)", ColorGreen, ColorReset, len(data))
		return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(fmt.Sprintf("Screenshot captured (%d KB base64). Data:\n%s", len(data)/1024, data))), nil
	}))
}

// must panics if tool registration fails.
func must(err error) {
	if err != nil {
		panic(err)
	}
}
