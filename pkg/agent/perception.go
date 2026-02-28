package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"strings"
	"time"

	openai "github.com/sashabaranov/go-openai"
	"github.com/playwright-community/playwright-go"
)

// Agent handles AI-driven element finding using any OpenAI-compatible API.
// Supports: OpenAI, Ollama, LM Studio, Groq, Together, Azure, or any
// endpoint that implements the /v1/chat/completions spec.
//
// Environment variables:
//   - AI_API_KEY   (required) — API key for the LLM provider
//   - AI_BASE_URL  (optional) — Custom base URL (default: https://api.openai.com/v1)
//   - AI_MODEL     (optional) — Model name (default: gpt-4o)
//
// Legacy: OPENAI_API_KEY is also accepted for backward compatibility.
type Agent struct {
	client *openai.Client
	model  string
	cache  *SemanticCache
}

// New creates a new Agent with LLM configuration from environment variables.
func New() (*Agent, error) {
	// API key: prefer AI_API_KEY, fallback to OPENAI_API_KEY
	apiKey := os.Getenv("AI_API_KEY")
	if apiKey == "" {
		apiKey = os.Getenv("OPENAI_API_KEY")
	}
	if apiKey == "" {
		return nil, fmt.Errorf("AI_API_KEY (or OPENAI_API_KEY) environment variable is not set")
	}

	// Model: prefer AI_MODEL, default to gpt-4o
	model := os.Getenv("AI_MODEL")
	if model == "" {
		model = "gpt-4o"
	}

	// Base URL: prefer AI_BASE_URL, default to OpenAI
	baseURL := os.Getenv("AI_BASE_URL")

	var client *openai.Client
	if baseURL != "" {
		config := openai.DefaultConfig(apiKey)
		config.BaseURL = baseURL
		client = openai.NewClientWithConfig(config)
		log.Printf("[AI] Using custom endpoint: %s (model: %s)", baseURL, model)
	} else {
		client = openai.NewClient(apiKey)
		log.Printf("[AI] Using OpenAI (model: %s)", model)
	}

	return &Agent{client: client, model: model, cache: NewSemanticCache()}, nil
}

// ─── System Prompt ───

const systemPrompt = `You are a web automation assistant. Your job is to find the CSS selector for a specific element on a web page based on its Accessibility Tree.

I will provide you with:
1. The Accessibility Tree (a compact text representation of all interactive and semantic elements).
2. A description of the element I want to find (e.g., "Search button", "Username input").

You MUST return a JSON object with exactly two fields:
{"selector": "<css-selector>", "confidence": <0.0-1.0>}

Rules for choosing selectors (in priority order):
1. Use #id if the element has a unique ID
2. Use [aria-label="..."] for labeled elements
3. Use [role="..."][name="..."] for ARIA roles
4. Use semantic selectors like button, input[type="..."], a[href="..."]
5. Use :text("...") if the element is uniquely identifiable by its text
6. Combine selectors for specificity if needed (e.g., form input[type="email"])
7. NEVER use fragile positional selectors like div > div > span:nth-child(3)

Confidence guidelines:
- 0.9-1.0: Exact match found (ID, unique aria-label, etc.)
- 0.7-0.89: Good match but could be ambiguous
- 0.5-0.69: Best guess, element might not be correct
- Below 0.5: Very uncertain

Examples:
---
Tree: "- button 'Sign Up' [role=button]"
Prompt: "Sign up button"
Answer: {"selector": "button:text('Sign Up')", "confidence": 0.95}
---
Tree: "- textbox 'Email address' [name=email] [id=email-input]"
Prompt: "Email field"  
Answer: {"selector": "#email-input", "confidence": 1.0}
---
Tree: "- link 'Learn more' [href=/about]"
Prompt: "About page link"
Answer: {"selector": "a[href='/about']", "confidence": 0.85}
---

Return ONLY the JSON object. No markdown, no explanation.`

// ─── Types ───

// selectorResult represents the LLM response for element finding
type selectorResult struct {
	Selector   string  `json:"selector"`
	Confidence float64 `json:"confidence"`
}

// ─── Accessibility Tree ───

// GetAccessibilityTree returns a cleaned ARIA snapshot of the page
func (a *Agent) GetAccessibilityTree(page playwright.Page) (string, error) {
	snapshot, err := page.Locator("body").AriaSnapshot()
	if err != nil {
		return "", fmt.Errorf("failed to get aria snapshot: %w", err)
	}
	return snapshot, nil
}

// cleanAccessibilityTree filters and compacts the AX tree to reduce token usage.
// Aggressively prunes decorative, image, and deeply-nested elements to keep
// the output under ~12K chars (fits within free-tier LLM token limits).
func cleanAccessibilityTree(tree string) string {
	lines := strings.Split(tree, "\n")
	var cleaned []string
	for _, line := range lines {
		trimmed := strings.TrimRight(line, " \t")
		if trimmed == "" {
			continue
		}

		lower := strings.ToLower(trimmed)

		// Skip decorative / low-value ARIA nodes
		if strings.Contains(lower, "presentation") && !strings.Contains(lower, "text") {
			continue
		}
		// Skip image nodes (e-commerce pages have hundreds)
		if strings.HasPrefix(strings.TrimLeft(lower, " -"), "img ") {
			continue
		}
		// Skip generic separators and dividers
		if strings.Contains(lower, "separator") {
			continue
		}
		// Skip empty group/list items with no meaningful text
		if (strings.HasSuffix(lower, "group:") || strings.HasSuffix(lower, "list:")) && len(trimmed) < 30 {
			continue
		}

		// Measure indentation depth (each 2 spaces = 1 level)
		indent := 0
		for _, ch := range trimmed {
			if ch == ' ' {
				indent++
			} else {
				break
			}
		}
		// Skip deeply nested elements (>6 levels) — usually noise
		if indent > 12 {
			continue
		}

		cleaned = append(cleaned, trimmed)
	}

	result := strings.Join(cleaned, "\n")

	// Smart truncation: keep first 12K chars to fit free-tier LLM limits
	// (~3K tokens for most models, well within Groq/OpenRouter/Gemini free tiers)
	if len(result) > 12000 {
		result = result[:12000] + "\n...(truncated — page has more content)"
	}

	return result
}

// ─── Element Finding ───

// FindElement uses LLM to find the selector for a given prompt, with retry and confidence scoring.
func (a *Agent) FindElement(page playwright.Page, userPrompt string) (string, error) {
	// Add smart fallback for when prompt is already a valid CSS/XPath selector
	if count, err := page.Locator(userPrompt).Count(); err == nil && count > 0 {
		log.Printf("[AI] SMART FALLBACK: Prompt '%s' is already a valid selector on the page. Bypassing LLM.", userPrompt)
		return userPrompt, nil
	}

	// 1. Check semantic cache first to avoid slow LLM lookup
	pageURL := page.URL()
	parsedURL, err := url.Parse(pageURL)
	domain := "unknown"
	if err == nil {
		domain = parsedURL.Hostname()
	}

	if cachedSelector, found := a.cache.Get(domain, userPrompt); found {
		log.Printf("[AI] CACHE HIT: Found cached selector '%s' for '%s' on %s", cachedSelector, userPrompt, domain)
		return cachedSelector, nil
	}

	const maxRetries = 3
	var lastErr error

	log.Printf("[AI]  Looking for element: '%s' (max %d attempts)...", userPrompt, maxRetries)

	for attempt := 1; attempt <= maxRetries; attempt++ {
		log.Printf("[AI] → Attempt %d/%d: snapshotting page...", attempt, maxRetries)
		selector, confidence, err := a.findElementOnce(page, userPrompt)
		if err != nil {
			lastErr = err
			if attempt < maxRetries {
				log.Printf("[AI] Attempt %d/%d failed: %v. Re-snapshotting in 1.5s...", attempt, maxRetries, err)
				time.Sleep(1500 * time.Millisecond)
			}
			continue
		}

		// Confidence check
		if confidence < 0.7 {
			lastErr = fmt.Errorf("low confidence %.2f for selector '%s'", confidence, selector)
			if attempt < maxRetries {
				log.Printf("[AI] Attempt %d/%d: low confidence (%.2f). Retrying...", attempt, maxRetries, confidence)
				time.Sleep(1500 * time.Millisecond)
			}
			continue
		}

		log.Printf("[AI]  Found selector '%s' (confidence: %.2f) on attempt %d", selector, confidence, attempt)

		// 2. Save high-confidence selector to cache for future interactions
		if confidence >= 0.8 {
			a.cache.Set(domain, userPrompt, selector)
		}

		return selector, nil
	}

	return "", fmt.Errorf("element not found after %d attempts: %w", maxRetries, lastErr)
}

// findElementOnce performs a single LLM call to find an element.
func (a *Agent) findElementOnce(page playwright.Page, userPrompt string) (string, float64, error) {
	// 1. Get and clean Accessibility Tree
	snapshotStr, err := a.GetAccessibilityTree(page)
	if err != nil {
		return "", 0, err
	}
	snapshotStr = cleanAccessibilityTree(snapshotStr)

	// 2. Build messages
	messages := []openai.ChatCompletionMessage{
		{
			Role:    openai.ChatMessageRoleSystem,
			Content: systemPrompt,
		},
		{
			Role:    openai.ChatMessageRoleUser,
			Content: fmt.Sprintf("Accessibility Tree:\n%s\n\nFind Element: %s", snapshotStr, userPrompt),
		},
	}

	// 3. Call LLM with base context because models like Kimi K2.5 take >40s to think
	var resp openai.ChatCompletionResponse
	for llmAttempt := 0; llmAttempt < 2; llmAttempt++ {
		log.Printf("[AI] → Calling %s API...", a.model)
		resp, err = a.client.CreateChatCompletion(
			context.Background(),
			openai.ChatCompletionRequest{
				Model:       a.model,
				Messages:    messages,
				Temperature: 1.0,
				MaxTokens:   1024,
			},
		)
		if err == nil {
			break
		}
		if llmAttempt == 0 {
			log.Printf("[AI] LLM call failed, retrying once: %v", err)
			time.Sleep(1 * time.Second)
		}
	}
	if err != nil {
		return "", 0, fmt.Errorf("LLM API error: %w", err)
	}

	if len(resp.Choices) == 0 {
		return "", 0, fmt.Errorf("no response from LLM")
	}

	// 4. Parse the JSON response
	raw := strings.TrimSpace(resp.Choices[0].Message.Content)
	// Clean up markdown if LLM disobeyed
	raw = strings.TrimPrefix(raw, "```json")
	raw = strings.TrimPrefix(raw, "```")
	raw = strings.TrimSuffix(raw, "```")
	raw = strings.TrimSpace(raw)

	var result selectorResult
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		// Fallback: try treating the raw response as a plain selector
		if raw == "NOT_FOUND" {
			return "", 0, fmt.Errorf("element not found by AI")
		}
		log.Printf("[AI] Warning: LLM returned non-JSON response, using as raw selector: %s", raw)
		return raw, 0.6, nil
	}

	if result.Selector == "" || result.Selector == "NOT_FOUND" {
		return "", 0, fmt.Errorf("element not found by AI")
	}

	return result.Selector, result.Confidence, nil
}
