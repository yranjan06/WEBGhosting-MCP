package agent

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sync"
)

// SemanticCache stores CSS selectors previously found by the AI for specific prompts on specific domains.
// This prevents the agent from making 40-second LLM calls for elements it already knows.
type SemanticCache struct {
	mu    sync.RWMutex
	store map[string]string // Key: "domain|prompt", Value: "selector"
	path  string
}

func NewSemanticCache() *SemanticCache {
	store := make(map[string]string)
	cachePath := ""

	// We'll store this in the user's home directory so it persists across server restarts
	homeDir, err := os.UserHomeDir()
	if err == nil {
		cacheDir := filepath.Join(homeDir, ".webmcp")
		os.MkdirAll(cacheDir, 0755)
		cachePath = filepath.Join(cacheDir, "semantic_cache.json")

		data, err := os.ReadFile(cachePath)
		if err == nil {
			if err := json.Unmarshal(data, &store); err != nil {
				log.Printf("[CACHE] Warning: Failed to parse existing cache: %v", err)
			} else {
				log.Printf("[CACHE] Loaded %d known selectors from disk", len(store))
			}
		}
	}

	return &SemanticCache{
		store: store,
		path:  cachePath,
	}
}

// Get retrieves a cached selector. Returns the selector and true if found.
func (c *SemanticCache) Get(domain, prompt string) (string, bool) {
	key := domain + "|" + prompt
	c.mu.RLock()
	defer c.mu.RUnlock()
	selector, exists := c.store[key]
	return selector, exists
}

// Set saves a selector to the cache and writes it to disk.
func (c *SemanticCache) Set(domain, prompt, selector string) {
	key := domain + "|" + prompt
	c.mu.Lock()
	defer c.mu.Unlock()
	c.store[key] = selector

	if c.path != "" {
		data, err := json.MarshalIndent(c.store, "", "  ")
		if err == nil {
			if err := os.WriteFile(c.path, data, 0644); err != nil {
				log.Printf("[CACHE] Warning: Failed to write to disk: %v", err)
			}
		}
	}
}
