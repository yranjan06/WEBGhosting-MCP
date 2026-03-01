package agent

import (
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/playwright-community/playwright-go"
)

// SubtaskResult contains the result of a parallel extraction task
type SubtaskResult struct {
	URL        string      `json:"url"`
	Data       string      `json:"data,omitempty"`
	Error      string      `json:"error,omitempty"`
	TimeMillis int64       `json:"time_millis"`
}

// ParallelExtract navigates to multiple URLs in parallel using isolated browser contexts
// and extracts data based on the provided schema.
func (a *Agent) ParallelExtract(pw *playwright.Playwright, browser playwright.Browser, urls []string, schema interface{}, modelOverride string) ([]SubtaskResult, error) {
	if a == nil {
		return nil, fmt.Errorf("AI agent not initialized")
	}

	results := make([]SubtaskResult, len(urls))
	var wg sync.WaitGroup
	
	// Limit concurrency to avoid crashing the browser or hitting rate limits too fast (max 3 at a time)
	sem := make(chan struct{}, 3)
	var resultsMu sync.Mutex

	for i, url := range urls {
		wg.Add(1)
		
		go func(index int, targetURL string) {
			defer wg.Done()
			sem <- struct{}{}        // Acquire
			defer func() { <-sem }() // Release

			start := time.Now()
			res := SubtaskResult{URL: targetURL}

			// 1. Create an isolated context for this subtask to avoid cookie/state bleed
			ctx, err := browser.NewContext(playwright.BrowserNewContextOptions{
				UserAgent: playwright.String("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"),
			})
			if err != nil {
				res.Error = fmt.Sprintf("failed to create context: %v", err)
				res.TimeMillis = time.Since(start).Milliseconds()
				recordResult(&resultsMu, results, index, res)
				return
			}
			defer ctx.Close()

			// 2. Create a new page
			page, err := ctx.NewPage()
			if err != nil {
				res.Error = fmt.Sprintf("failed to create page: %v", err)
				res.TimeMillis = time.Since(start).Milliseconds()
				recordResult(&resultsMu, results, index, res)
				return
			}
			
			// 3. Navigate
			log.Printf("[PARALLEL] Worker %d navigating to %s...", index, targetURL)
			if _, err := page.Goto(targetURL, playwright.PageGotoOptions{
				WaitUntil: playwright.WaitUntilStateDomcontentloaded,
				Timeout:   playwright.Float(30000), // 30s timeout
			}); err != nil {
				res.Error = fmt.Sprintf("navigation failed: %v", err)
				res.TimeMillis = time.Since(start).Milliseconds()
				recordResult(&resultsMu, results, index, res)
				return
			}

			// Give it a brief moment to render SPA content
			page.WaitForTimeout(2000)

			// 4. Extract Data
			log.Printf("[PARALLEL] Worker %d extracting data from %s...", index, targetURL)
			extractedJSON, err := a.ExtractData(page, schema, modelOverride)
			if err != nil {
				res.Error = fmt.Sprintf("extraction failed: %v", err)
			} else {
				res.Data = extractedJSON
			}

			res.TimeMillis = time.Since(start).Milliseconds()
			recordResult(&resultsMu, results, index, res)
			log.Printf("[PARALLEL] Worker %d finished %s in %dms", index, targetURL, res.TimeMillis)

		}(i, url)
	}

	wg.Wait()
	return results, nil
}

func recordResult(mu *sync.Mutex, results []SubtaskResult, index int, res SubtaskResult) {
	mu.Lock()
	defer mu.Unlock()
	results[index] = res
}
