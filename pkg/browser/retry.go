package browser

import (
	"fmt"
	"log"
	"time"
)

// RetryWithBackoff retries the given function up to maxAttempts times with exponential backoff.
// baseDelay is doubled after each failed attempt. It logs each retry.
func RetryWithBackoff(maxAttempts int, baseDelay time.Duration, fn func() error) error {
	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		lastErr = fn()
		if lastErr == nil {
			return nil
		}
		if attempt == maxAttempts {
			break
		}
		delay := baseDelay * time.Duration(1<<uint(attempt-1)) // exponential: base * 2^(attempt-1)
		log.Printf("[RETRY] Attempt %d/%d failed: %v. Retrying in %v...", attempt, maxAttempts, lastErr, delay)
		time.Sleep(delay)
	}
	return fmt.Errorf("failed after %d attempts: %w", maxAttempts, lastErr)
}
