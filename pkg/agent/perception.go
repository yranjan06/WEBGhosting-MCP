package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/JohannesKaufmann/html-to-markdown/v2/converter"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/base"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/commonmark"
	"github.com/kaptinlin/jsonrepair"
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

// Improved system prompt with few-shot examples and confidence scoring
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

// selectorResult represents the LLM response for element finding
type selectorResult struct {
	Selector   string  `json:"selector"`
	Confidence float64 `json:"confidence"`
}

// GetAccessibilityTree returns a cleaned ARIA snapshot of the page
func (a *Agent) GetAccessibilityTree(page playwright.Page) (string, error) {
	snapshot, err := page.Locator("body").AriaSnapshot()
	if err != nil {
		return "", fmt.Errorf("failed to get aria snapshot: %w", err)
	}
	return snapshot, nil
}

// cleanAccessibilityTree filters and compacts the AX tree to reduce token usage.
func cleanAccessibilityTree(tree string) string {
	lines := strings.Split(tree, "\n")
	var cleaned []string
	for _, line := range lines {
		trimmed := strings.TrimRight(line, " \t")
		if trimmed == "" {
			continue
		}
		lower := strings.ToLower(trimmed)
		if strings.Contains(lower, "presentation") && !strings.Contains(lower, "text") {
			continue
		}
		cleaned = append(cleaned, trimmed)
	}

	result := strings.Join(cleaned, "\n")

	// Smart truncation: keep first 40K chars
	if len(result) > 40000 {
		result = result[:40000] + "\n...(truncated — page has more content)"
	}

	return result
}

// FindElement uses LLM to find the selector for a given prompt, with retry and confidence scoring.
func (a *Agent) FindElement(page playwright.Page, userPrompt string) (string, error) { // Add smart fallback for when prompt is already a valid CSS/XPath selector
	if count, err := page.Locator(userPrompt).Count(); err == nil && count > 0 {
		log.Printf("[AI] ⚡ SMART FALLBACK: Prompt '%s' is already a valid selector on the page. Bypassing LLM.", userPrompt)
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
		log.Printf("[AI] ⚡ CACHE HIT: Found cached selector '%s' for '%s' on %s", cachedSelector, userPrompt, domain)
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

const extractSystemPrompt = "You are an expert data extractor. From the given markdown, extract ALL requested structured data.\nReturn ONLY a valid JSON object. No explanation, no markdown formatting (like ```json), no extra text."

// callExtractionLLM handles the HTTP retry logic for LLM APIs
func (a *Agent) callExtractionLLM(actualModel string, messages []map[string]interface{}, temperature float32, responseFormat map[string]interface{}) (string, error) {
	baseURL := os.Getenv("AI_BASE_URL")
	apiKey := os.Getenv("AI_API_KEY")

	if extModel := os.Getenv("EXTRACTION_MODEL"); extModel != "" {
		actualModel = extModel
		if extAPIKey := os.Getenv("EXTRACTION_API_KEY"); extAPIKey != "" {
			apiKey = extAPIKey
		}
		if extBase := os.Getenv("EXTRACTION_BASE_URL"); extBase != "" {
			baseURL = extBase
		} else if os.Getenv("OPENAI_API_KEY") != "" && strings.Contains(strings.ToLower(actualModel), "gpt") {
			baseURL = "https://api.openai.com/v1"
			apiKey = os.Getenv("OPENAI_API_KEY")
		}
	} else if baseURL == "" {
		baseURL = "https://api.openai.com/v1"
	}

	payload := map[string]interface{}{
		"model":       actualModel,
		"messages":    messages,
		"temperature": temperature,
		"max_tokens":  8192,
	}

	if responseFormat != nil {
		payload["response_format"] = responseFormat
	}

	if strings.Contains(strings.ToLower(actualModel), "kimi") {
		payload["chat_template_kwargs"] = map[string]interface{}{"thinking": true}
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("payload marshal error: %w", err)
	}

	var result map[string]interface{}
	var apiErr error
	maxRetries := 3

	for attempt := 1; attempt <= maxRetries; attempt++ {
		if attempt > 1 {
			backoff := time.Duration(math.Pow(2, float64(attempt-1))) * time.Second
			time.Sleep(backoff)
		}

		ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
		req, err := http.NewRequestWithContext(ctx, "POST", baseURL+"/chat/completions", bytes.NewReader(payloadBytes))
		if err != nil {
			cancel()
			return "", fmt.Errorf("request create error: %w", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+apiKey)
		// Bypass localtunnel completely for programmatic API calls
		req.Header.Set("Bypass-Tunnel-Reminder", "true")

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			apiErr = fmt.Errorf("extraction API error: %w", err)
			cancel()
			continue
		}

		if resp.StatusCode != 200 {
			apiErr = fmt.Errorf("API error: status %d", resp.StatusCode)
			resp.Body.Close()
			cancel()
			continue
		}

		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			apiErr = fmt.Errorf("decode error: %w", err)
			resp.Body.Close()
			cancel()
			continue
		}

		resp.Body.Close()
		cancel()
		apiErr = nil
		break
	}

	if apiErr != nil {
		return "", fmt.Errorf("extraction failed after %d attempts: %w", maxRetries, apiErr)
	}

	choices, ok := result["choices"].([]interface{})
	if !ok || len(choices) == 0 {
		return "", fmt.Errorf("no response from LLM")
	}

	choice := choices[0].(map[string]interface{})
	msg := choice["message"].(map[string]interface{})
	raw, _ := msg["content"].(string)

	raw = strings.TrimSpace(raw)
	raw = strings.TrimPrefix(raw, "```json")
	raw = strings.TrimPrefix(raw, "```")
	raw = strings.TrimSuffix(raw, "```")
	raw = strings.TrimSpace(raw)

	return raw, nil
}

// ExtractData uses a Map-Reduce architecture to extract structured data.
func (a *Agent) ExtractData(page playwright.Page, schema interface{}, modelOverride string) (string, error) {
	// W3C WebMCP Integration (Chrome 146+ incubation)
	// If the website natively exposes structured MCP tools, we can eventually bypass brittle DOM scraping entirely.
	hasWebMCP, err := page.Evaluate(`() => typeof navigator !== 'undefined' && typeof navigator.modelContext !== 'undefined'`)
	if err == nil && hasWebMCP == true {
		log.Printf("\033[32m[AI] 🌐 Native W3C WebMCP Support Detected!\033[0m Future routing will bypass DOM pruning to execute registered native tools.")
	}

	// 1. Prune the HTML
	js := `() => {
		const clone = document.body.cloneNode(true);
		const removeSelectors = [
			'script', 'style', 'noscript', 'iframe', 'svg', 'path', 
			'symbol', 'defs', 'clipPath', 'g', 'header', 'footer', 
			'nav', 'aside', 'form', 'button', 'input', 'select', 
			'textarea', 'meta', 'link',
			'[aria-hidden="true"]', '[data-test-id]', '.visually-hidden',
			'.hidden', '[style*="display: none"]', 'img[src^="data:"]',
			'img[loading="lazy"]', '[role="presentation"]', '[data-artdeco-is-hidden="true"]',
			'.global-nav', '.scaffold-layout__aside', '.artdeco-empty-state'
		];
		removeSelectors.forEach(sel => {
			clone.querySelectorAll(sel).forEach(el => el.remove());
		});
		return clone.innerHTML;
	}`

	log.Printf("[AI] → Pruning HTML DOM for extraction...")
	rawHTMLObj, err := page.Evaluate(js)
	if err != nil {
		return "", fmt.Errorf("failed to evaluate JS for HTML pruning: %w", err)
	}

	rawHTML, ok := rawHTMLObj.(string)
	if !ok {
		return "", fmt.Errorf("failed to cast pruned HTML to string")
	}

	// 2. Convert to compact Markdown natively in Go
	log.Printf("[AI] → Converting pruned HTML to clean Markdown...")
	conv := converter.NewConverter(
		converter.WithPlugins(
			base.NewBasePlugin(),
			commonmark.NewCommonmarkPlugin(),
		),
	)
	mdText, err := conv.ConvertString(rawHTML)
	if err != nil {
		log.Printf("[AI] Warning: HTML to Markdown conversion failed, falling back to innerText: %v", err)
		mdText, _ = page.Locator("body").InnerText()
	}

	log.Printf("[AI] Extraction context reduced to %d characters of Markdown", len(mdText))

	// Format schema instruction
	var schemaInstruction string
	var jsonSchemaMap map[string]interface{}

	switch s := schema.(type) {
	case string:
		schemaInstruction = s
	case map[string]interface{}:
		schemaBytes, _ := json.MarshalIndent(s, "", "  ")
		schemaInstruction = "Extract data matching this JSON Schema structure. Return a pure JSON array containing the extracted objects. If the Markdown chunk contains NO relevant data for this schema, you MUST return an empty array `[]` exactly. Do not explain or echo the schema.\nSchema:\n" + string(schemaBytes)
		jsonSchemaMap = s
	default:
		return "", fmt.Errorf("invalid schema type: must be string or JSON object")
	}

	// STEP 1: Boundary Detection (LLM Map Phase)
	log.Printf("[AI] → Step 1: LLM Map Phase - Identifying chunk boundaries...")
	boundaryPrompt := `Analyze this markdown and identify the exact repeating string sequence or Markdown block that marks the start of a new item requested by the schema.
Return ONLY that exact string marker in a JSON format: {"marker": "string"}`

	// Pass a small snippet (400 chars) for fast marker detection
	snippetLimit := 800 // Keeping snippet limit slightly larger to ensure boundary is found, but changing chunk size
	if len(mdText) < snippetLimit {
		snippetLimit = len(mdText)
	}
	
	boundaryMessages := []map[string]interface{}{
		{"role": "system", "content": "You are a boundary detection agent."},
		{"role": "user", "content": fmt.Sprintf("Markdown Sample:\n%s\n\nSchema:\n%s\n\n%s", mdText[:snippetLimit], schemaInstruction, boundaryPrompt)},
	}

	marker := ""
	markerJSON, err := a.callExtractionLLM(a.model, boundaryMessages, 0.0, map[string]interface{}{"type": "json_object"})
	if err == nil {
		var boundaryResult map[string]string
		if err := json.Unmarshal([]byte(markerJSON), &boundaryResult); err == nil {
			marker = boundaryResult["marker"]
		} else {
			log.Printf("[AI] ⚠️ Boundary parse failed.")
		}
	} else {
		log.Printf("[AI] ⚠️ Boundary detection API failed, relying on hard chunking fallback.")
	}

	var chunks []string

	// STEP 2: Go-level Document Chunking
	if marker != "" && len(mdText) > 5000 {
		log.Printf("[AI] → Step 2: Splitting document by logical boundary marker: '%s'", marker)
		rawPieces := strings.Split(mdText, marker)
		// Group pieces into chunks of roughly 400 chars to optimize parallel processing
		currentChunk := ""
		for _, piece := range rawPieces {
			if len(currentChunk)+len(piece) > 400 {
				chunks = append(chunks, currentChunk)
				currentChunk = piece
			} else {
				currentChunk += marker + piece
			}
		}
		if currentChunk != "" {
			chunks = append(chunks, currentChunk)
		}
		log.Printf("[AI] Document logically split into %d chunks.", len(chunks))
	} else {
		// Hard Fallback Splitting (if no marker found or API timed out)
		log.Printf("[AI] → Step 2: Applying programmatic fallback chunking (max 2000 chars/chunk)...")
		chunkSize := 2000
		
		lines := strings.Split(mdText, "\n")
		currentChunk := ""
		for _, line := range lines {
			if len(currentChunk)+len(line) > chunkSize && currentChunk != "" {
				chunks = append(chunks, currentChunk)
				currentChunk = line + "\n"
			} else {
				currentChunk += line + "\n"
			}
		}
		if currentChunk != "" {
			chunks = append(chunks, currentChunk)
		}
		log.Printf("[AI] Document programmatically split gently into %d chunks.", len(chunks))
	}

	// STEP 3: Parallelized Extraction
	log.Printf("[AI] → Step 3: Map-Reduce Parallel Extraction (%d chunks)...", len(chunks))
	
	type chunkResult struct {
		index int
		data  string
		err   error
	}
	resultsChan := make(chan chunkResult, len(chunks))

	var responseFormat map[string]interface{}
	if jsonSchemaMap != nil {
		responseFormat = map[string]interface{}{"type": "json_object"}
	}

	actualModel := a.model
	if modelOverride != "" {
		actualModel = modelOverride
	}

	// Semaphore to limit concurrent LLM API calls and prevent 429 Too Many Requests limits
	concurrencyLimit := 5
	sem := make(chan struct{}, concurrencyLimit)

	for i, chunkText := range chunks {
		// Acquire token
		sem <- struct{}{}

		go func(idx int, text string) {
			defer func() { <-sem }() // Release token when done

			chunkMessages := []map[string]interface{}{
				{"role": "system", "content": extractSystemPrompt},
				{"role": "user", "content": fmt.Sprintf("Chunk Markdown:\n%s\n\nRequested Instructions:\n%s", text, schemaInstruction)},
			}
			data, err := a.callExtractionLLM(actualModel, chunkMessages, 0.0, responseFormat)
			resultsChan <- chunkResult{index: idx, data: data, err: err}
		}(i, chunkText)
	}

	// Collect and Flatten parallel results
	log.Printf("[AI] → Step 4: Stitching and Merging %d successfully parsed JSON data chunks...", len(resultsChan))
	
	var masterArray []interface{}
	
	for i := 0; i < len(chunks); i++ {
		res := <-resultsChan
		if res.err != nil {
			log.Printf("[AI] ⚠️ Chunk %d extraction failed: %v", res.index, res.err)
			continue
		}
		
		repairedJSON, err := jsonrepair.JSONRepair(res.data)
		if err != nil {
			repairedJSON = res.data // Use raw if repair fails
		}
		
		var chunkArray []interface{}
		if err := json.Unmarshal([]byte(repairedJSON), &chunkArray); err == nil {
			// It's a valid JSON array, append its elements
			masterArray = append(masterArray, chunkArray...)
		} else {
			// Might be a single JSON object instead of an array
			var chunkObject map[string]interface{}
			if err := json.Unmarshal([]byte(repairedJSON), &chunkObject); err == nil {
				masterArray = append(masterArray, chunkObject)
			} else {
				log.Printf("[AI] ⚠️ Chunk %d output was not a valid JSON array/object, skipping.", res.index)
			}
		}
	}

	finalMegaBytes, _ := json.MarshalIndent(masterArray, "", "  ")
	finalMegaJSON := string(finalMegaBytes)
	
	return finalMegaJSON, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
