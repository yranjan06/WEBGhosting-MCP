package browser

import (
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/playwright-community/playwright-go"
	"github.com/ranjanyadav/web-mcp/pkg/stealth"
)

// TabInfo holds metadata about a browser tab.
type TabInfo struct {
	Index int    `json:"index"`
	Title string `json:"title"`
	URL   string `json:"url"`
}

// NetworkRequest holds a captured HTTP request/response pair.
type NetworkRequest struct {
	Method     string `json:"method"`
	URL        string `json:"url"`
	Status     int    `json:"status,omitempty"`
	StatusText string `json:"status_text,omitempty"`
}

type Engine struct {
	pw          *playwright.Playwright
	browser     playwright.Browser
	context     playwright.BrowserContext
	Stealth     *stealth.StealthConfig
	initMu      sync.Mutex
	initialized bool
	initErr     error
	CDPEndpoint string

	// Multi-tab support
	pagesMu   sync.Mutex
	pages     []playwright.Page
	activeTab int

	// Console logs
	logsMu      sync.Mutex
	consoleLogs []string

	// Network request tracking
	netMu           sync.Mutex
	networkRequests []NetworkRequest

	// Dialog handling
	dialogAction string // "accept" or "dismiss"

	// Status tracking for visibility
	statMu         sync.Mutex
	lastAction     string
	lastActionTime time.Time
}

func New(cdpEndpoint string) (*Engine, error) {
	return &Engine{
		Stealth:         stealth.DefaultConfig(),
		CDPEndpoint:     cdpEndpoint,
		consoleLogs:     make([]string, 0),
		networkRequests: make([]NetworkRequest, 0),
		pages:           make([]playwright.Page, 0),
		activeTab:       0,
		dialogAction:    "accept",
		lastAction:      "none",
		lastActionTime:  time.Now(),
	}, nil
}

// setupPageListeners attaches console, dialog, and network listeners to a page.
func (e *Engine) setupPageListeners(page playwright.Page) {
	page.OnConsole(func(msg playwright.ConsoleMessage) {
		e.logsMu.Lock()
		defer e.logsMu.Unlock()
		if len(e.consoleLogs) >= 100 {
			e.consoleLogs = e.consoleLogs[1:]
		}
		e.consoleLogs = append(e.consoleLogs, fmt.Sprintf("[%s] %s", msg.Type(), msg.Text()))
	})

	// Network request tracking
	page.OnRequest(func(req playwright.Request) {
		e.netMu.Lock()
		defer e.netMu.Unlock()
		if len(e.networkRequests) >= 200 {
			e.networkRequests = e.networkRequests[1:]
		}
		e.networkRequests = append(e.networkRequests, NetworkRequest{
			Method: req.Method(),
			URL:    req.URL(),
		})
	})

	page.OnResponse(func(resp playwright.Response) {
		e.netMu.Lock()
		defer e.netMu.Unlock()
		// Update the last matching request with response status
		for i := len(e.networkRequests) - 1; i >= 0; i-- {
			if e.networkRequests[i].URL == resp.URL() && e.networkRequests[i].Status == 0 {
				e.networkRequests[i].Status = resp.Status()
				e.networkRequests[i].StatusText = resp.StatusText()
				break
			}
		}
	})

	page.OnDialog(func(dialog playwright.Dialog) {
		e.logsMu.Lock()
		action := e.dialogAction
		e.logsMu.Unlock()

		log.Printf("[BROWSER] Dialog appeared (%s): %s. Action: %s", dialog.Type(), dialog.Message(), action)

		e.logsMu.Lock()
		e.consoleLogs = append(e.consoleLogs, fmt.Sprintf("[DIALOG] Type: %s, Message: %s, Action Taken: %s", dialog.Type(), dialog.Message(), action))
		e.logsMu.Unlock()

		if action == "dismiss" {
			dialog.Dismiss()
		} else {
			dialog.Accept()
		}
	})
}

func (e *Engine) EnsureInitialized() error {
	e.initMu.Lock()
	defer e.initMu.Unlock()

	if e.initialized {
		alive := false
		e.pagesMu.Lock()
		if len(e.pages) > 0 && !e.pages[0].IsClosed() {
			alive = true
		}
		e.pagesMu.Unlock()

		if alive {
			return e.initErr
		}

		log.Println("[BROWSER] Connection lost or page closed. Initiating auto-recovery...")
		e.Close()
		e.initialized = false
		e.pw = nil
		e.browser = nil
		e.context = nil
		e.pagesMu.Lock()
		e.pages = make([]playwright.Page, 0)
		e.activeTab = 0
		e.pagesMu.Unlock()
	}

	e.initialized = true
	log.Println("[BROWSER] Initializing Playwright...")

	pw, err := playwright.Run()
	if err != nil {
		e.initErr = fmt.Errorf("could not start playwright: %v", err)
		return e.initErr
	}
	e.pw = pw

	var browser playwright.Browser
	var context playwright.BrowserContext

	if e.CDPEndpoint != "" {
		log.Printf("[BROWSER] Connecting to existing browser at %s...", e.CDPEndpoint)
		browser, err = pw.Chromium.ConnectOverCDP(e.CDPEndpoint)
		if err != nil {
			e.initErr = fmt.Errorf("could not connect over CDP: %v", err)
			return e.initErr
		}
		log.Println("[BROWSER] Connected to existing browser session.")
		e.browser = browser

		contexts := browser.Contexts()
		if len(contexts) > 0 {
			context = contexts[0]
		} else {
			context, err = browser.NewContext()
			if err != nil {
				e.initErr = fmt.Errorf("could not create context: %v", err)
				return e.initErr
			}
		}
		e.context = context

	} else {
		headless := false
		if os.Getenv("BROWSER_HEADLESS") == "true" {
			headless = true
		}

		proxyServer := os.Getenv("HTTP_PROXY")
		var proxy *playwright.Proxy
		if proxyServer != "" {
			proxy = &playwright.Proxy{Server: proxyServer}
			proxyUser := os.Getenv("PROXY_USERNAME")
			proxyPass := os.Getenv("PROXY_PASSWORD")
			if proxyUser != "" && proxyPass != "" {
				proxy.Username = playwright.String(proxyUser)
				proxy.Password = playwright.String(proxyPass)
			}
			log.Printf("[BROWSER] Using proxy server: %s", proxyServer)
		}

		userDataDir := os.Getenv("BROWSER_USER_DATA_DIR")
		if userDataDir != "" {
			log.Printf("[BROWSER] Using persistent user data dir: %s", userDataDir)
			launchOpts := playwright.BrowserTypeLaunchPersistentContextOptions{
				Headless: playwright.Bool(headless),
				Args: []string{
					"--disable-blink-features=AutomationControlled",
				},
				UserAgent: playwright.String("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"),
			}
			if proxy != nil {
				launchOpts.Proxy = proxy
			}

			context, err = pw.Chromium.LaunchPersistentContext(userDataDir, launchOpts)
			if err != nil {
				e.initErr = fmt.Errorf("could not launch persistent context: %v", err)
				return e.initErr
			}
			e.context = context
		} else {
			launchOptions := playwright.BrowserTypeLaunchOptions{
				Headless: playwright.Bool(headless),
				Args: []string{
					"--disable-blink-features=AutomationControlled",
				},
			}
			if proxy != nil {
				launchOptions.Proxy = proxy
			}

			browser, err = pw.Chromium.Launch(launchOptions)
			if err != nil {
				e.initErr = fmt.Errorf("could not launch browser: %v", err)
				return e.initErr
			}
			e.browser = browser

			context, err = browser.NewContext(playwright.BrowserNewContextOptions{
				UserAgent: playwright.String("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"),
			})
			if err != nil {
				e.initErr = fmt.Errorf("could not create context: %v", err)
				return e.initErr
			}
			e.context = context
		}
	}

	// Try to get an existing page or create a new one
	pages := e.context.Pages()
	var page playwright.Page
	if len(pages) > 0 {
		page = pages[0]
	} else {
		page, err = e.context.NewPage()
		if err != nil {
			e.initErr = fmt.Errorf("could not create page: %v", err)
			return e.initErr
		}
	}

	// Setup listeners and stealth for the first tab
	e.setupPageListeners(page)
	if err := e.Stealth.Apply(page); err != nil {
		log.Printf("Warning: Failed to apply stealth: %v", err)
	}

	e.pagesMu.Lock()
	e.pages = append(e.pages, page)
	e.activeTab = 0
	e.pagesMu.Unlock()

	log.Println("[BROWSER] Ready.")
	return e.initErr
}

// activePage returns the currently active page (thread-safe).
func (e *Engine) activePage() playwright.Page {
	e.pagesMu.Lock()
	defer e.pagesMu.Unlock()
	if e.activeTab < 0 || e.activeTab >= len(e.pages) {
		return nil
	}
	return e.pages[e.activeTab]
}

func (e *Engine) Close() {
	if e.context != nil {
		e.context.Close()
	}
	if e.browser != nil {
		e.browser.Close()
	}
	if e.pw != nil {
		e.pw.Stop()
	}
}

// SetLastAction records the most recent tool action for status reporting.
func (e *Engine) SetLastAction(action string) {
	e.statMu.Lock()
	defer e.statMu.Unlock()
	e.lastAction = action
	e.lastActionTime = time.Now()
}

// StatusInfo contains current browser state for reporting.
type StatusInfo struct {
	Initialized    bool   `json:"initialized"`
	ActiveTabURL   string `json:"active_tab_url"`
	ActiveTabTitle string `json:"active_tab_title"`
	TabCount       int    `json:"tab_count"`
	LastAction     string `json:"last_action"`
	SecondsSince   int    `json:"seconds_since_last_action"`
}

// GetStatus returns a snapshot of the current browser state.
func (e *Engine) GetStatus() StatusInfo {
	e.statMu.Lock()
	lastAction := e.lastAction
	lastActionTime := e.lastActionTime
	e.statMu.Unlock()

	e.initMu.Lock()
	initialized := e.initialized
	e.initMu.Unlock()

	info := StatusInfo{
		Initialized:  initialized,
		LastAction:   lastAction,
		SecondsSince: int(time.Since(lastActionTime).Seconds()),
	}

	e.pagesMu.Lock()
	info.TabCount = len(e.pages)
	e.pagesMu.Unlock()

	page := e.activePage()
	if page != nil && !page.IsClosed() {
		info.ActiveTabURL = page.URL()
		title, _ := page.Title()
		info.ActiveTabTitle = title
	}

	return info
}

func (e *Engine) Navigate(url string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	_, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
	})

	// Auto-recovery check on navigation failure
	if err != nil && (strings.Contains(err.Error(), "target closed") || strings.Contains(err.Error(), "Target page, context or browser has been closed")) {
		log.Println("[BROWSER] Target closed during navigation. Forcing re-initialization...")
		e.initMu.Lock()
		e.initialized = false
		e.initMu.Unlock()

		if retryErr := e.EnsureInitialized(); retryErr != nil {
			return fmt.Errorf("auto-recovery failed: %v", retryErr)
		}

		page = e.activePage()
		if page != nil {
			_, err = page.Goto(url, playwright.PageGotoOptions{
				WaitUntil: playwright.WaitUntilStateDomcontentloaded,
			})
		}
	}

	return err
}

func (e *Engine) Page() (playwright.Page, error) {
	if err := e.EnsureInitialized(); err != nil {
		return nil, err
	}
	page := e.activePage()
	if page == nil {
		return nil, fmt.Errorf("no active tab")
	}
	return page, nil
}

func (e *Engine) SetDialogAction(action string) {
	e.logsMu.Lock()
	defer e.logsMu.Unlock()
	e.dialogAction = action
}

func (e *Engine) GetConsoleLogs() []string {
	e.logsMu.Lock()
	defer e.logsMu.Unlock()
	logs := make([]string, len(e.consoleLogs))
	copy(logs, e.consoleLogs)
	return logs
}

func (e *Engine) ClearConsoleLogs() {
	e.logsMu.Lock()
	defer e.logsMu.Unlock()
	e.consoleLogs = make([]string, 0)
}

func (e *Engine) WaitForSelector(selector string, state string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	if state == "" {
		state = "visible"
	}

	validStates := map[string]*playwright.WaitForSelectorState{
		"attached": playwright.WaitForSelectorStateAttached,
		"detached": playwright.WaitForSelectorStateDetached,
		"visible":  playwright.WaitForSelectorStateVisible,
		"hidden":   playwright.WaitForSelectorStateHidden,
	}

	pwState, ok := validStates[state]
	if !ok {
		return fmt.Errorf("invalid state '%s', must be one of: attached, detached, visible, hidden", state)
	}

	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	_, err := page.WaitForSelector(selector, playwright.PageWaitForSelectorOptions{
		State:   pwState,
		Timeout: playwright.Float(30000),
	})
	return err
}

func (e *Engine) WaitForLoadState(state string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	if state == "" {
		state = "load"
	}

	switch state {
	case "load", "domcontentloaded", "networkidle":
		// Valid
	default:
		return fmt.Errorf("invalid load state '%s', must be one of: load, domcontentloaded, networkidle", state)
	}

	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	ls := playwright.LoadState(state)
	return page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
		State:   &ls,
		Timeout: playwright.Float(30000),
	})
}

func (e *Engine) ExecuteScript(script string) (string, error) {
	if err := e.EnsureInitialized(); err != nil {
		return "", err
	}

	page := e.activePage()
	if page == nil {
		return "", fmt.Errorf("no active tab")
	}
	result, err := page.Evaluate(script)
	if err != nil {
		return "", err
	}

	if result == nil {
		return "null", nil
	}
	return fmt.Sprintf("%v", result), nil
}

func (e *Engine) PressKey(key string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	return page.Keyboard().Press(key)
}

// HumanType types text character-by-character with human-like delays.
func (e *Engine) HumanType(selector, text string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	return HumanTypeText(page, selector, text)
}

// HumanClickElement clicks an element with human-like mouse movement and hesitation.
func (e *Engine) HumanClickElement(selector string) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	return HumanClick(page, selector)
}

// HumanScrollPage scrolls the page naturally.
func (e *Engine) HumanScrollPage(direction string, amount int) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	return HumanScroll(page, direction, amount)
}

// ─── Multi-tab Management ───

// OpenTab creates a new browser tab and returns its index.
func (e *Engine) OpenTab() (int, error) {
	if err := e.EnsureInitialized(); err != nil {
		return -1, err
	}

	page, err := e.context.NewPage()
	if err != nil {
		return -1, fmt.Errorf("could not create new tab: %w", err)
	}

	// Apply stealth and listeners to new tab
	e.setupPageListeners(page)
	if err := e.Stealth.Apply(page); err != nil {
		log.Printf("Warning: Failed to apply stealth to new tab: %v", err)
	}

	e.pagesMu.Lock()
	e.pages = append(e.pages, page)
	idx := len(e.pages) - 1
	e.activeTab = idx // Auto-switch to new tab
	e.pagesMu.Unlock()

	log.Printf("[TABS] Opened new tab (index: %d)", idx)
	return idx, nil
}

// SwitchTab switches the active tab to the given index.
func (e *Engine) SwitchTab(index int) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}

	e.pagesMu.Lock()
	defer e.pagesMu.Unlock()

	if index < 0 || index >= len(e.pages) {
		return fmt.Errorf("invalid tab index %d (have %d tabs)", index, len(e.pages))
	}
	e.activeTab = index

	// Bring tab to front
	if err := e.pages[index].BringToFront(); err != nil {
		log.Printf("Warning: could not bring tab %d to front: %v", index, err)
	}

	log.Printf("[TABS] Switched to tab %d", index)
	return nil
}

// CloseTab closes the tab at the given index.
func (e *Engine) CloseTab(index int) error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}

	e.pagesMu.Lock()
	defer e.pagesMu.Unlock()

	if index < 0 || index >= len(e.pages) {
		return fmt.Errorf("invalid tab index %d (have %d tabs)", index, len(e.pages))
	}
	if len(e.pages) <= 1 {
		return fmt.Errorf("cannot close the last remaining tab")
	}

	// Close the page
	if err := e.pages[index].Close(); err != nil {
		return fmt.Errorf("failed to close tab %d: %w", index, err)
	}

	// Remove from slice
	e.pages = append(e.pages[:index], e.pages[index+1:]...)

	// Adjust activeTab
	if e.activeTab >= len(e.pages) {
		e.activeTab = len(e.pages) - 1
	} else if e.activeTab > index {
		e.activeTab--
	}

	log.Printf("[TABS] Closed tab %d (active: %d)", index, e.activeTab)
	return nil
}

// ListTabs returns info about all open tabs.
func (e *Engine) ListTabs() ([]TabInfo, error) {
	if err := e.EnsureInitialized(); err != nil {
		return nil, err
	}

	e.pagesMu.Lock()
	defer e.pagesMu.Unlock()

	tabs := make([]TabInfo, len(e.pages))
	for i, page := range e.pages {
		title, _ := page.Title()
		tabs[i] = TabInfo{
			Index: i,
			Title: title,
			URL:   page.URL(),
		}
	}
	return tabs, nil
}

// ─── Navigation History ───

// GoBack navigates the active tab to the previous page.
func (e *Engine) GoBack() error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	_, err := page.GoBack()
	return err
}

// GoForward navigates the active tab to the next page.
func (e *Engine) GoForward() error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	_, err := page.GoForward()
	return err
}

// ─── Network Monitoring ───

// GetNetworkRequests returns captured HTTP requests.
func (e *Engine) GetNetworkRequests() []NetworkRequest {
	e.netMu.Lock()
	defer e.netMu.Unlock()
	reqs := make([]NetworkRequest, len(e.networkRequests))
	copy(reqs, e.networkRequests)
	return reqs
}

// ClearNetworkRequests resets the captured request log.
func (e *Engine) ClearNetworkRequests() {
	e.netMu.Lock()
	defer e.netMu.Unlock()
	e.networkRequests = make([]NetworkRequest, 0)
}
