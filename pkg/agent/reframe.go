package agent

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	openai "github.com/sashabaranov/go-openai"
)

// ─── Reframed Prompt ───

// ReframedPrompt is the structured output from the reframe pipeline.

type ReframedPrompt struct {
	// ClearTask is the reframed, English, unambiguous description of what the user wants.
	ClearTask string `json:"clear_task"`

	// OriginalPrompt preserves the raw user input for logging/debugging.
	OriginalPrompt string `json:"original_prompt"`

	// Intent is the classified user intent: navigate, click, type, extract, search, scroll, multi_step.
	Intent string `json:"intent"`

	// RequiredSteps are the MCP tool names likely needed (e.g., ["browse", "extract"]).
	RequiredSteps []string `json:"required_steps"`

	// TargetElement is a clear English description of the UI element (for click/type intents).
	TargetElement string `json:"target_element,omitempty"`

	// TargetURL is the resolved URL if the user's intent involves navigation.
	TargetURL string `json:"target_url,omitempty"`

	// Language is the detected source language of the user's prompt.
	Language string `json:"language"`

	// Confidence is 0.0-1.0 indicating how well the reframer understood the intent.
	Confidence float64 `json:"confidence"`

	// WasReframed indicates whether the prompt was actually transformed (false if already clean English).
	WasReframed bool `json:"was_reframed"`

	// PageContextHint is injected page context (page type, visible elements) if available.
	PageContextHint string `json:"page_context_hint,omitempty"`
}

// ─── Reframe Cache ───

// reframeCache avoids re-calling LLM for identical or near-identical prompts.
type reframeCacheEntry struct {
	result    ReframedPrompt
	timestamp time.Time
}

var (
	reframeCacheMu  sync.RWMutex
	reframeCache    = make(map[string]reframeCacheEntry)
	reframeCacheTTL = 5 * time.Minute // cached reframes last 5 minutes
)

func reframeCacheKey(prompt, pageContext string) string {
	h := sha256.Sum256([]byte(prompt + "|" + pageContext))
	return fmt.Sprintf("%x", h[:16])
}

// ─── CO-STAR System Prompt ───
// Context, Objective, Style, Tone, Audience, Response format

const reframeSystemPrompt = `You are WEBGhosting's Prompt Reframer — an intelligent preprocessor that converts casual, multilingual, vague user prompts into precise, structured commands for a browser automation system.

**Context (C):**
You sit between the user and a stealth browser MCP server with 33 tools: browse, click, type, extract, scroll, screenshot, run_task, fill_form, press_key, etc. Users write in Hindi, Hinglish, broken English, or any language. Their requests are often vague, incomplete, or use slang.

**Objective (O):**
Transform the raw user prompt into a clear, unambiguous English task description that the downstream tools can execute perfectly. Classify the intent, identify required tools, and resolve ambiguity.

**Style (S):**
Be concise and precise. Output clean JSON only. No filler words in clear_task.

**Tone (T):**
Technical and action-oriented. Every word in clear_task should be actionable.

**Audience (A):**
The downstream consumer is an MCP tool dispatcher (not a human). It needs: exact intent, target elements, and required tool sequence.

**Response Format (R):**
Return ONLY a valid JSON object with these exact fields:
{
  "clear_task": "Precise English description of the task",
  "intent": "navigate|click|type|extract|search|scroll|screenshot|multi_step",
  "required_steps": ["tool1", "tool2"],
  "target_element": "Clear description of the UI element (if click/type intent)",
  "target_url": "Resolved URL (if navigate intent)",
  "language": "Detected input language (e.g., Hindi, Hinglish, English, Spanish)",
  "confidence": 0.95,
  "was_reframed": true
}

**Intent Classification Rules:**
- "navigate" → User wants to go to a URL/website (required_steps: ["browse"])
- "click" → User wants to click something (required_steps: ["click"])
- "type" → User wants to type/enter text (required_steps: ["type"] or ["fill_form"])
- "extract" → User wants to get/scrape/read data (required_steps: ["extract"] or ["get_page_context", "extract"])
- "search" → User wants to search for something (required_steps: ["fill_form", "press_key"])
- "scroll" → User wants to scroll (required_steps: ["scroll"])
- "screenshot" → User wants a visual capture (required_steps: ["screenshot"])
- "multi_step" → Complex task needing multiple actions (required_steps: ["run_task"])

**Translation Rules:**
- Translate ALL non-English text to English
- "daba do" / "press karo" / "click karo" → click intent
- "likh do" / "type karo" / "daal do" → type intent  
- "khol do" / "open karo" / "jao" → navigate intent
- "nikal do" / "extract karo" / "bata do" / "dikha do" → extract intent
- "dhundh do" / "search karo" / "find karo" → search intent
- "upar/neeche" / "scroll karo" → scroll intent
- "wo wala" / "that one" → resolve using page_context if provided
- "bhai" / "yaar" / "please" → strip filler, keep intent

**Ambiguity Resolution:**
- If vague element reference ("wo button", "that thing"), use page_context_hint to resolve
- If URL is implied ("reddit pe jao"), expand to full URL (https://www.reddit.com)
- If multiple intents detected, pick primary intent, rest go to required_steps
- Common sites: "HN" → https://news.ycombinator.com, "reddit" → https://www.reddit.com, "flipkart" → https://www.flipkart.com, "amazon" → https://www.amazon.in

**Important:**
- Return ONLY the JSON object. No markdown, no explanation, no backtick fences.
- If the prompt is already clear English with obvious intent, still return the structured JSON but set was_reframed to false.
- Confidence < 0.6 means you're genuinely unsure about the intent.`

// ─── Skip Detection (fast path) ───

// needsReframe checks if a prompt needs LLM reframing or can be passed through directly.
// Returns false for prompts that are already clean, structured English with clear intent.
func needsReframe(prompt string) bool {
	prompt = strings.TrimSpace(prompt)

	// Empty or very short prompts — pass through
	if len(prompt) < 3 {
		return false
	}

	// Already a URL — no reframe needed
	lower := strings.ToLower(prompt)
	if strings.HasPrefix(lower, "http://") || strings.HasPrefix(lower, "https://") {
		return false
	}

	// Already a CSS selector — no reframe needed
	if strings.HasPrefix(prompt, "#") || strings.HasPrefix(prompt, ".") ||
		strings.HasPrefix(prompt, "[") || strings.Contains(prompt, "::") {
		return false
	}

	// Check for non-ASCII characters (likely non-English)
	for _, r := range prompt {
		if r > 127 {
			return true // Has Unicode chars → likely needs translation
		}
	}

	// Check for common Hindi/Hinglish words that need reframing
	hindiMarkers := []string{
		"karo", "kro", "kardo", "kar do", "bhai", "yaar", "bata", "batao",
		"daba", "dabao", "press karo", "khol", "kholo", "daal", "daalo",
		"likh", "likho", "nikal", "nikalo", "dhundh", "dhundho", "jao",
		"dikhao", "dikha", "wala", "wali", "wale", "mein", "pe", "ko",
		"hai", "ho", "hoga", "chahiye", "de do", "dedo", "kr do", "krdo",
		"wo ", "upar", "neeche", "aur", "phir", "pehle", "baad",
		"seedha", "sidha", "kaise", "kya", "kaha", "kidhar",
	}
	for _, marker := range hindiMarkers {
		if strings.Contains(lower, marker) {
			return true
		}
	}

	// Check for common slang/casual patterns
	casualMarkers := []string{
		"plz", "pls", "asap", "idk", "nvm", "tbh", "imo", "fyi",
		"gimme", "gonna", "wanna", "gotta", "lemme", "dunno",
	}
	for _, marker := range casualMarkers {
		if strings.Contains(lower, marker) {
			return true
		}
	}

	// If prompt is short and vague (< 5 words, no clear verb), reframe it
	words := strings.Fields(prompt)
	if len(words) <= 3 {
		// Short prompts like "top stories" or "login button" might need context
		return true
	}

	// Default: don't reframe clean English prompts
	return false
}

// ─── Core Reframe Function ───

// ReframePrompt takes a raw user prompt (any language, any quality) and returns
// a structured, precise, English ReframedPrompt ready for the tool dispatcher.
//
// Fast path: If the prompt is already clean English with obvious intent, bypasses LLM.
// Slow path: Uses a fast/cheap LLM call (~200ms) for translation + intent extraction.
func (a *Agent) ReframePrompt(rawPrompt string, pageContext string) (*ReframedPrompt, error) {
	rawPrompt = strings.TrimSpace(rawPrompt)

	// ─── Fast path: already clean, skip LLM ───
	if !needsReframe(rawPrompt) {
		log.Printf("[REFRAME] FAST PATH: Prompt is already clean, skipping LLM")
		return &ReframedPrompt{
			ClearTask:      rawPrompt,
			OriginalPrompt: rawPrompt,
			Intent:         classifyIntentLocal(rawPrompt),
			RequiredSteps:  inferStepsLocal(rawPrompt),
			Language:       "English",
			Confidence:     0.9,
			WasReframed:    false,
		}, nil
	}

	// ─── Cache check ───
	cacheKey := reframeCacheKey(rawPrompt, pageContext)
	reframeCacheMu.RLock()
	if entry, ok := reframeCache[cacheKey]; ok && time.Since(entry.timestamp) < reframeCacheTTL {
		reframeCacheMu.RUnlock()
		log.Printf("[REFRAME] CACHE HIT for prompt: '%s'", truncate(rawPrompt, 50))
		return &entry.result, nil
	}
	reframeCacheMu.RUnlock()

	// ─── Slow path: LLM reframe ───
	log.Printf("[REFRAME] Reframing prompt: '%s'", truncate(rawPrompt, 80))

	// Build user message with optional page context
	userMsg := rawPrompt
	if pageContext != "" {
		userMsg = fmt.Sprintf("Page Context: %s\n\nUser Prompt: %s", pageContext, rawPrompt)
	}

	messages := []openai.ChatCompletionMessage{
		{
			Role:    openai.ChatMessageRoleSystem,
			Content: reframeSystemPrompt,
		},
		{
			Role:    openai.ChatMessageRoleUser,
			Content: userMsg,
		},
	}

	// Use a faster/cheaper model for reframing if available
	reframeModel := os.Getenv("REFRAME_MODEL")
	if reframeModel == "" {
		reframeModel = a.model // fallback to main model
	}

	var resp openai.ChatCompletionResponse
	var err error

	// Single LLM call with 1 retry (reframe should be fast)
	for attempt := 0; attempt < 2; attempt++ {
		resp, err = a.client.CreateChatCompletion(
			context.Background(),
			openai.ChatCompletionRequest{
				Model:       reframeModel,
				Messages:    messages,
				Temperature: 0.1, // Low temperature for consistent reframing
				MaxTokens:   512, // Reframe output is small
			},
		)
		if err == nil {
			break
		}
		if attempt == 0 {
			log.Printf("[REFRAME] LLM call failed, retrying: %v", err)
			time.Sleep(500 * time.Millisecond)
		}
	}
	if err != nil {
		// Fallback: return raw prompt with local classification if LLM fails
		log.Printf("[REFRAME] LLM failed, using local fallback: %v", err)
		return &ReframedPrompt{
			ClearTask:      rawPrompt,
			OriginalPrompt: rawPrompt,
			Intent:         classifyIntentLocal(rawPrompt),
			RequiredSteps:  inferStepsLocal(rawPrompt),
			Language:       "unknown",
			Confidence:     0.5,
			WasReframed:    false,
		}, nil
	}

	if len(resp.Choices) == 0 {
		return nil, fmt.Errorf("no response from reframe LLM")
	}

	// Parse JSON response
	raw := strings.TrimSpace(resp.Choices[0].Message.Content)
	raw = strings.TrimPrefix(raw, "```json")
	raw = strings.TrimPrefix(raw, "```")
	raw = strings.TrimSuffix(raw, "```")
	raw = strings.TrimSpace(raw)

	var result ReframedPrompt
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		log.Printf("[REFRAME] Failed to parse LLM response as JSON: %v. Raw: %s", err, truncate(raw, 200))
		// Fallback: use raw LLM text as clear_task
		return &ReframedPrompt{
			ClearTask:      raw,
			OriginalPrompt: rawPrompt,
			Intent:         classifyIntentLocal(rawPrompt),
			RequiredSteps:  inferStepsLocal(rawPrompt),
			Language:       "unknown",
			Confidence:     0.6,
			WasReframed:    true,
		}, nil
	}

	// Fill in missing fields
	result.OriginalPrompt = rawPrompt
	if result.ClearTask == "" {
		result.ClearTask = rawPrompt
	}
	if result.Intent == "" {
		result.Intent = classifyIntentLocal(rawPrompt)
	}
	if len(result.RequiredSteps) == 0 {
		result.RequiredSteps = inferStepsLocal(rawPrompt)
	}

	log.Printf("[REFRAME] ✓ '%s' → '%s' (intent: %s, confidence: %.2f, lang: %s)",
		truncate(rawPrompt, 40), truncate(result.ClearTask, 60), result.Intent, result.Confidence, result.Language)

	// ─── Cache the result ───
	reframeCacheMu.Lock()
	reframeCache[cacheKey] = reframeCacheEntry{result: result, timestamp: time.Now()}
	reframeCacheMu.Unlock()

	return &result, nil
}

// ─── Local Fallback Functions (no LLM needed) ───

// classifyIntentLocal uses keyword matching to classify intent when LLM is unavailable.
func classifyIntentLocal(prompt string) string {
	lower := strings.ToLower(prompt)

	// Navigation
	if strings.HasPrefix(lower, "http") || strings.HasPrefix(lower, "www.") ||
		containsAny(lower, []string{"go to", "open", "navigate", "visit", "browse to", "jao", "khol"}) {
		return "navigate"
	}
	// Click
	if containsAny(lower, []string{"click", "press", "tap", "hit", "daba", "dabao", "press karo"}) {
		return "click"
	}
	// Type
	if containsAny(lower, []string{"type", "enter", "input", "fill", "write", "likh", "daal", "likho"}) {
		return "type"
	}
	// Extract
	if containsAny(lower, []string{"extract", "scrape", "get", "read", "fetch", "nikal", "bata", "dikha", "show"}) {
		return "extract"
	}
	// Search
	if containsAny(lower, []string{"search", "find", "look for", "query", "dhundh", "dhundho"}) {
		return "search"
	}
	// Scroll
	if containsAny(lower, []string{"scroll", "swipe", "upar", "neeche"}) {
		return "scroll"
	}
	// Screenshot
	if containsAny(lower, []string{"screenshot", "capture", "snap", "photo"}) {
		return "screenshot"
	}

	return "multi_step"
}

// inferStepsLocal maps intents to likely required MCP tool names.
func inferStepsLocal(prompt string) []string {
	intent := classifyIntentLocal(prompt)
	switch intent {
	case "navigate":
		return []string{"browse"}
	case "click":
		return []string{"click"}
	case "type":
		return []string{"type"}
	case "extract":
		return []string{"get_page_context", "extract"}
	case "search":
		return []string{"fill_form", "press_key"}
	case "scroll":
		return []string{"scroll"}
	case "screenshot":
		return []string{"screenshot"}
	case "multi_step":
		return []string{"run_task"}
	default:
		return []string{"run_task"}
	}
}

// ─── Helpers ───

// containsAny checks if s contains any of the given substrings.
func containsAny(s string, subs []string) bool {
	for _, sub := range subs {
		if strings.Contains(s, sub) {
			return true
		}
	}
	return false
}

// truncate shortens a string to maxLen with "..." suffix.
func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
