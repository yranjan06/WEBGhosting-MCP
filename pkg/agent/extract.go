package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/JohannesKaufmann/html-to-markdown/v2/converter"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/base"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/commonmark"
	"github.com/kaptinlin/jsonrepair"
	"github.com/playwright-community/playwright-go"
)

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
		log.Printf("\033[32m[AI] Native W3C WebMCP Support Detected!\033[0m Future routing will bypass DOM pruning to execute registered native tools.")
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
			log.Printf("[AI] WARNING: Boundary parse failed.")
		}
	} else {
		log.Printf("[AI] WARNING: Boundary detection API failed, relying on hard chunking fallback.")
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

	return finalMegaJSON, nil
}
