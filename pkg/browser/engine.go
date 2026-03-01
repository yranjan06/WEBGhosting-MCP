package browser

import (
	"encoding/json"
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

	// Stealth Configuration
	Humanize bool

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
		Humanize:        true,
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

// GetBrowserInstances returns the underlying Playwright and Browser objects
// for use in isolated parallel context creation.
func (e *Engine) GetBrowserInstances() (*playwright.Playwright, playwright.Browser, error) {
	if err := e.EnsureInitialized(); err != nil {
		return nil, nil, err
	}
	return e.pw, e.browser, nil
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
	if !e.Humanize {
		return page.Locator(selector).Fill(text)
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
	if !e.Humanize {
		return page.Locator(selector).Click()
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
	if !e.Humanize {
		deltaY := float64(amount)
		if direction == "up" {
			deltaY = -deltaY
		}
		return page.Mouse().Wheel(0, deltaY)
	}
	return HumanScroll(page, direction, amount)
}

// ScrollToBottom scrolls the page completely to the bottom dynamically.
func (e *Engine) ScrollToBottom() error {
	if err := e.EnsureInitialized(); err != nil {
		return err
	}
	page := e.activePage()
	if page == nil {
		return fmt.Errorf("no active tab")
	}
	if !e.Humanize {
		_, err := page.Evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
		return err
	}
	return HumanScrollToBottom(page)
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

// ─── Screenshot ───

// Screenshot captures the current page as base64-encoded PNG.
func (e *Engine) Screenshot() (string, error) {
	if err := e.EnsureInitialized(); err != nil {
		return "", err
	}
	page := e.activePage()
	if page == nil {
		return "", fmt.Errorf("no active tab")
	}
	data, err := page.Screenshot(playwright.PageScreenshotOptions{
		FullPage: playwright.Bool(false),
	})
	if err != nil {
		return "", fmt.Errorf("screenshot failed: %w", err)
	}
	encoded := base64Encode(data)
	return encoded, nil
}

func base64Encode(data []byte) string {
	const b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var result []byte
	for i := 0; i < len(data); i += 3 {
		var b uint32
		remaining := len(data) - i
		if remaining >= 3 {
			b = uint32(data[i])<<16 | uint32(data[i+1])<<8 | uint32(data[i+2])
			result = append(result, b64[(b>>18)&0x3F], b64[(b>>12)&0x3F], b64[(b>>6)&0x3F], b64[b&0x3F])
		} else if remaining == 2 {
			b = uint32(data[i])<<16 | uint32(data[i+1])<<8
			result = append(result, b64[(b>>18)&0x3F], b64[(b>>12)&0x3F], b64[(b>>6)&0x3F], '=')
		} else {
			b = uint32(data[i]) << 16
			result = append(result, b64[(b>>18)&0x3F], b64[(b>>12)&0x3F], '=', '=')
		}
	}
	return string(result)
}

// ─── Page Context ───

// PageContext holds structured metadata about the current page for LLM agent planning.
type PageContext struct {
	URL             string   `json:"url"`
	Title           string   `json:"title"`
	PageType        string   `json:"page_type"`
	TextLength      int      `json:"text_length"`
	LinkCount       int      `json:"link_count"`
	ImageCount      int      `json:"image_count"`
	FormCount       int      `json:"form_count"`
	ButtonCount     int      `json:"button_count"`
	InputCount      int      `json:"input_count"`
	HasSearch       bool     `json:"has_search"`
	HasLogin        bool     `json:"has_login"`
	HasReviews      bool     `json:"has_reviews"`
	HasPagination   bool     `json:"has_pagination"`
	HasVideo        bool     `json:"has_video"`
	HasCart         bool     `json:"has_cart"`
	MainHeadings    []string `json:"main_headings"`
	MetaDescription string   `json:"meta_description"`
	Summary         string   `json:"summary"`
}

// GetPageContext analyzes the current page and returns structured context.
// This is a zero-LLM, pure JS analysis that helps LLM agents plan their next steps.
func (e *Engine) GetPageContext() (*PageContext, error) {
	if err := e.EnsureInitialized(); err != nil {
		return nil, err
	}
	page := e.activePage()
	if page == nil {
		return nil, fmt.Errorf("no active tab")
	}

	// Run comprehensive page analysis in one JS evaluation
	script := `() => {
		const body = document.body;
		const text = body ? body.innerText : '';

		// Count elements
		const links = document.querySelectorAll('a[href]').length;
		const images = document.querySelectorAll('img').length;
		const forms = document.querySelectorAll('form').length;
		const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]').length;
		const inputs = document.querySelectorAll('input, textarea, select').length;

		// Detect features
		const lowerText = text.toLowerCase();
		const lowerHTML = body ? body.innerHTML.toLowerCase() : '';
		const url = window.location.href.toLowerCase();
		const title = document.title.toLowerCase();

		const hasSearch = !!document.querySelector('input[type="search"], [role="search"], input[placeholder*="search" i], input[name*="search" i], input[aria-label*="search" i]');

		// Login detection: check for password fields OR sign-in/login as primary page purpose
		const hasPasswordField = !!document.querySelector('input[type="password"]');
		const isLoginTitle = !!(title.match(/log.?in|sign.?in/) || document.querySelector('h1, h2')?.textContent?.toLowerCase().match(/sign.?in|log.?in/));
		const hasLogin = hasPasswordField || (isLoginTitle && inputs <= 5);

		// Reviews: require ACTUAL review DOM structure, not just text mentions
		// This prevents false positives on GitHub (★ stars), Reddit (ratings), Wikipedia
		const hasReviewElements = !!document.querySelector(
			'[data-hook*="review"], [class*="customer-review"], [class*="user-review"], ' +
			'[class*="ReviewCard"], [class*="reviewText"], [class*="review-content"], ' +
			'[id*="customer_review"], [id*="reviewsMedley"], [class*="review-rating"]'
		);
		const hasReviews = hasReviewElements;

		const hasPagination = !!document.querySelector(
			'[class*="pagination"], [class*="pager"], nav[aria-label*="pagination" i], ' +
			'a[aria-label*="next" i], a[aria-label*="Next" i], ' +
			'[class*="s-pagination"], a.morelink'
		);
		const hasVideo = !!document.querySelector('video, iframe[src*="youtube"], iframe[src*="vimeo"], ytd-video-renderer, [class*="video-player"]');
		const hasCart = !!(lowerHTML.match(/add.?to.?cart|buy.?now|add.?to.?bag/) && document.querySelector('button, [role="button"]'));

		// Page type detection — ordered by specificity (most specific first)
		let pageType = 'unknown';

		// 1. Blank pages
		if (url === 'about:blank' || url.startsWith('chrome://') || url.startsWith('data:')) {
			pageType = 'blank';
		}
		// 2. Login/signup pages (SPA: works for Twitter, LinkedIn, Facebook etc)
		else if (isLoginTitle && text.length < 5000) {
			pageType = 'login_page';
		}
		else if (hasPasswordField && forms > 0 && text.length < 5000) {
			pageType = 'login_page';
		}
		// 3. Search results
		else if (url.includes('/search') || url.match(/[?&](q|k|query|keyword)=/) || title.includes('search results')) {
			pageType = 'search_results';
		}
		// 4. Product pages (e-commerce)
		else if (hasCart && (hasReviews || lowerHTML.match(/price|mrp|buy/))) {
			pageType = 'product_page';
		}
		// 5. Social media feeds (BEFORE article — Reddit/YouTube have <article> tags)
		else if (url.includes('reddit.com') || url.includes('twitter.com') || url.includes('x.com') ||
				 url.includes('facebook.com') || url.includes('instagram.com')) {
			pageType = hasLogin ? 'login_page' : 'social_feed';
		}
		// 6. Known platforms
		else if (url.includes('youtube.com') || url.includes('youtu.be')) {
			pageType = hasLogin ? 'login_page' : 'video_platform';
		}
		else if (url.includes('github.com')) {
			pageType = 'code_repository';
		}
		else if (url.includes('stackoverflow.com') || url.includes('stackexchange.com')) {
			pageType = url.match(/\/questions\/\d+/) ? 'qa_page' : 'listing_page';
		}
		// 7. Articles (long-form content — Wikipedia, blogs, news)
		else if (url.match(/\/(article|blog|post|news|wiki)\//i)) {
			pageType = 'article';
		}
		else if (document.querySelector('[class*="article-body"], [class*="post-content"], [class*="mw-parser-output"]')) {
			pageType = 'article';
		}
		else if (text.length > 5000 && links < text.length / 50) {
			pageType = 'article';
		}
		// 8. Review pages (dedicated review sections)
		else if (hasReviews && !hasCart) {
			pageType = 'review_page';
		}
		// 9. Form-heavy pages (require >2 forms to avoid cookie consent false positives)
		else if (forms > 2 && inputs > 5) {
			pageType = 'form_page';
		}
		// 10. Listing pages (many links, content-rich)
		else if (links > 15) {
			pageType = 'listing_page';
		}
		// 11. General fallback
		else {
			pageType = 'general';
		}

		// Get main headings
		const headings = [];
		document.querySelectorAll('h1, h2').forEach((h, i) => {
			if (i < 5 && h.textContent.trim()) headings.push(h.textContent.trim().substring(0, 80));
		});

		// Meta description
		const metaDesc = (document.querySelector('meta[name="description"]') || {}).content || '';

		// Brief summary (first 200 chars of visible text, cleaned)
		const summary = text.replace(/\s+/g, ' ').trim().substring(0, 200);

		return JSON.stringify({
			url: window.location.href,
			title: document.title,
			page_type: pageType,
			text_length: text.length,
			link_count: links,
			image_count: images,
			form_count: forms,
			button_count: buttons,
			input_count: inputs,
			has_search: hasSearch,
			has_login: hasLogin,
			has_reviews: hasReviews,
			has_pagination: hasPagination,
			has_video: hasVideo,
			has_cart: hasCart,
			main_headings: headings,
			meta_description: metaDesc.substring(0, 160),
			summary: summary
		});
	}`

	result, err := page.Evaluate(script)
	if err != nil {
		return nil, fmt.Errorf("page context analysis failed: %w", err)
	}

	var ctx PageContext
	if str, ok := result.(string); ok {
		if err := json.Unmarshal([]byte(str), &ctx); err != nil {
			return nil, fmt.Errorf("failed to parse page context: %w", err)
		}
	}

	return &ctx, nil
}
