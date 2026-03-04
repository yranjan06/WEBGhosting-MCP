package agent

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/JohannesKaufmann/html-to-markdown/v2/converter"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/base"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/commonmark"
	"github.com/kaptinlin/jsonrepair"
	"github.com/playwright-community/playwright-go"
)

// ─── Extraction Cache ───

type cacheEntry struct {
	result    string
	timestamp time.Time
}

var (
	extractionCache   = make(map[string]cacheEntry)
	extractionCacheMu sync.RWMutex
	cacheTTL          = 60 * time.Second
)

func cacheKey(url, schema string) string {
	h := sha256.Sum256([]byte(url + "|" + schema))
	return fmt.Sprintf("%x", h[:16])
}

const extractSystemPrompt = "You are an expert data extractor. From the given markdown, extract ALL requested structured data.\nReturn ONLY a valid JSON object. No explanation, no markdown formatting (like ```json), no extra text."

// chunkResult holds the result of a single chunk extraction.
type chunkResult struct {
	index int
	data  string
	err   error
}

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
		"max_tokens":  2500,
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
	hasWebMCP, err := page.Evaluate(`() => typeof navigator !== 'undefined' && typeof navigator.modelContext !== 'undefined'`)
	if err == nil && hasWebMCP == true {
		log.Printf("\033[32m[AI] Native W3C WebMCP Support Detected!\033[0m Future routing will bypass DOM pruning to execute registered native tools.")
	}

	// Extraction Cache: same URL + schema within 60s = instant return
	pageURL := page.URL()
	schemaJSON, _ := json.Marshal(schema)
	ck := cacheKey(pageURL, string(schemaJSON))

	extractionCacheMu.RLock()
	if entry, ok := extractionCache[ck]; ok && time.Since(entry.timestamp) < cacheTTL {
		extractionCacheMu.RUnlock()
		log.Printf("[AI] Cache HIT for %s — returning cached result", pageURL)
		return entry.result, nil
	}
	extractionCacheMu.RUnlock()

	// 1. Prune the HTML — aggressive DOM cleaning to minimize token usage.
	// Goal: reduce a 300K+ page to < 10K chars of meaningful text content.
	js := `() => {
		const clone = document.body.cloneNode(true);

		// Phase 1: Remove entire elements that never contain extractable text
		const removeSelectors = [
			'script', 'style', 'noscript', 'iframe', 'svg', 'path',
			'symbol', 'defs', 'clipPath', 'g', 'canvas', 'video', 'audio',
			'header', 'footer', 'nav', 'aside',
			'form', 'button', 'input', 'select', 'textarea', 'label',
			'meta', 'link', 'source', 'picture',
			'img',
			'[aria-hidden="true"]', '[role="presentation"]', '[role="banner"]',
			'[role="navigation"]', '[role="complementary"]', '[role="contentinfo"]',
			'[data-testid]', '[data-test-id]', '[data-artdeco-is-hidden="true"]',
			'[style*="display: none"]', '[style*="display:none"]',
			'[style*="visibility: hidden"]', '[style*="visibility:hidden"]',
			'.visually-hidden', '.sr-only', '.hidden', '.hide',
			'.ad', '.ads', '.advertisement', '.sponsored',
			'.cookie-banner', '.cookie-consent', '.modal', '.popup', '.overlay',
			'.breadcrumb', '.pagination', '.sidebar', '.widget',
			'.social-share', '.share-buttons',
			'.global-nav', '.scaffold-layout__aside', '.artdeco-empty-state'
		];
		removeSelectors.forEach(sel => {
			try { clone.querySelectorAll(sel).forEach(el => el.remove()); } catch(e) {}
		});

		// Phase 2: Strip all inline styles and data-* attributes (massive bloat)
		clone.querySelectorAll('*').forEach(el => {
			el.removeAttribute('style');
			el.removeAttribute('class');
			el.removeAttribute('id');
			[...el.attributes].forEach(attr => {
				if (attr.name.startsWith('data-') || attr.name.startsWith('aria-')
					|| attr.name === 'jsaction' || attr.name === 'jscontroller'
					|| attr.name === 'jsname' || attr.name === 'jsmodel') {
					el.removeAttribute(attr.name);
				}
			});
		});

		// Phase 3: Remove empty containers (divs/spans with no text content)
		clone.querySelectorAll('div, span, section, article').forEach(el => {
			if (el.textContent.trim().length === 0) el.remove();
		});

		// Phase 4: Collapse whitespace in the final output
		return clone.innerHTML
			.replace(/\s{2,}/g, ' ')
			.replace(/>\s+</g, '><')
			.trim();
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

	log.Printf("[AI] Extraction context: %d characters of Markdown", len(mdText))

	// InnerText fallback: if Markdown is still too large (>15K), use pure text
	// This strips ALL HTML structure, giving us just the visible text
	if len(mdText) > 15000 {
		log.Printf("[AI] Markdown too large (%d chars). Falling back to innerText for speed...", len(mdText))
		innerText, itErr := page.Locator("body").InnerText()
		if itErr == nil && len(innerText) > 0 && len(innerText) < len(mdText) {
			mdText = innerText
			log.Printf("[AI] InnerText fallback: reduced to %d characters", len(mdText))
		}
	}

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
			log.Printf("[AI] WARNING: Boundary parse failed.")
		}
	} else {
		log.Printf("[AI] WARNING: Boundary detection API failed, relying on hard chunking fallback.")
	}

	var chunks []string
	const maxChunkSize = 2000

	// STEP 2: Go-level Document Chunking
	if marker != "" && len(mdText) > 5000 {
		log.Printf("[AI] → Step 2: Splitting document by logical boundary marker: '%s'", marker)
		rawPieces := strings.Split(mdText, marker)

		for _, piece := range rawPieces {
			piece = strings.TrimSpace(piece)
			if piece == "" {
				continue
			}
			// If this piece is small enough, add it directly
			if len(piece) <= maxChunkSize {
				chunks = append(chunks, piece)
			} else {
				// Sub-chunk oversized pieces by newlines
				subChunks := splitByLines(piece, maxChunkSize)
				chunks = append(chunks, subChunks...)
			}
		}
		log.Printf("[AI] Document logically split into %d chunks.", len(chunks))
	} else {
		// Hard Fallback Splitting (if no marker found or API timed out)
		log.Printf("[AI] → Step 2: Applying programmatic fallback chunking (max %d chars/chunk)...", maxChunkSize)
		chunks = splitByLines(mdText, maxChunkSize)
		log.Printf("[AI] Document programmatically split gently into %d chunks.", len(chunks))
	}

	// STEP 3: Parallelized Extraction
	log.Printf("[AI] → Step 3: Map-Reduce Parallel Extraction (%d chunks)...", len(chunks))

	resultsChan := make(chan chunkResult, len(chunks))

	var responseFormat map[string]interface{}
	if jsonSchemaMap != nil {
		responseFormat = map[string]interface{}{"type": "json_object"}
	}

	actualModel := a.model
	if modelOverride != "" {
		actualModel = modelOverride
	}

	// Adaptive rate limiter: adjusts concurrency on 429 errors
	rl := NewAdaptiveRateLimiter(3)

	for i, chunkText := range chunks {
		rl.Acquire()

		go func(idx int, text string) {
			chunkMessages := []map[string]interface{}{
				{"role": "system", "content": extractSystemPrompt},
				{"role": "user", "content": fmt.Sprintf("Chunk Markdown:\n%s\n\nRequested Instructions:\n%s", text, schemaInstruction)},
			}
			data, err := a.callExtractionLLM(actualModel, chunkMessages, 0.0, responseFormat)
			if err != nil && strings.Contains(err.Error(), "429") {
				rl.OnRateLimit()
			}
			rl.Release()
			resultsChan <- chunkResult{index: idx, data: data, err: err}
		}(i, chunkText)
	}

	// Collect and Flatten parallel results
	log.Printf("[AI] → Step 4: Stitching and Merging %d successfully parsed JSON data chunks...", len(resultsChan))

	var masterArray []interface{}

	for i := 0; i < len(chunks); i++ {
		res := <-resultsChan
		if res.err != nil {
			log.Printf("[AI] WARNING: Chunk %d extraction failed: %v", res.index, res.err)
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
				log.Printf("[AI] WARNING: Chunk %d output was not a valid JSON array/object, skipping.", res.index)
			}
		}
	}

	finalMegaBytes, _ := json.MarshalIndent(masterArray, "", "  ")
	finalMegaJSON := string(finalMegaBytes)

	// Store in extraction cache
	extractionCacheMu.Lock()
	extractionCache[ck] = cacheEntry{result: finalMegaJSON, timestamp: time.Now()}
	extractionCacheMu.Unlock()

	return finalMegaJSON, nil
}

// splitByLines splits text into chunks of at most maxSize characters,
// breaking at newline boundaries to preserve readability.
func splitByLines(text string, maxSize int) []string {
	var chunks []string
	lines := strings.Split(text, "\n")
	currentChunk := ""
	for _, line := range lines {
		if len(currentChunk)+len(line)+1 > maxSize && currentChunk != "" {
			chunks = append(chunks, strings.TrimSpace(currentChunk))
			currentChunk = line + "\n"
		} else {
			currentChunk += line + "\n"
		}
	}
	if strings.TrimSpace(currentChunk) != "" {
		chunks = append(chunks, strings.TrimSpace(currentChunk))
	}
	return chunks
}
