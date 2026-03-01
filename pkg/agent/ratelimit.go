package agent

import (
	"log"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"
)

// AdaptiveRateLimiter dynamically adjusts concurrency based on API response patterns.
// On 429 errors, it reduces concurrency and increases inter-request delay.
// On success streaks, it gradually recovers.
type AdaptiveRateLimiter struct {
	sem           chan struct{}
	mu            sync.Mutex
	maxConcurrent int
	curConcurrent int
	successCount  int64
	baseDelay     time.Duration
	rateLimited   atomic.Bool
}

// NewAdaptiveRateLimiter creates a rate limiter starting at the given concurrency.
func NewAdaptiveRateLimiter(maxConcurrent int) *AdaptiveRateLimiter {
	rl := &AdaptiveRateLimiter{
		sem:           make(chan struct{}, maxConcurrent),
		maxConcurrent: maxConcurrent,
		curConcurrent: maxConcurrent,
		baseDelay:     200 * time.Millisecond,
	}
	// Fill semaphore
	for i := 0; i < maxConcurrent; i++ {
		rl.sem <- struct{}{}
	}
	return rl
}

// Acquire blocks until a slot is available. Adds jitter delay if rate limited.
func (rl *AdaptiveRateLimiter) Acquire() {
	<-rl.sem
	if rl.rateLimited.Load() {
		// Add jitter delay when rate limited: baseDelay + random(0, baseDelay)
		jitter := time.Duration(rand.Int63n(int64(rl.baseDelay)))
		time.Sleep(rl.baseDelay + jitter)
	}
}

// Release returns a slot to the pool.
func (rl *AdaptiveRateLimiter) Release() {
	rl.sem <- struct{}{}
	atomic.AddInt64(&rl.successCount, 1)

	// Recovery: after 10 consecutive successes, try to increase concurrency
	if atomic.LoadInt64(&rl.successCount) >= 10 {
		rl.mu.Lock()
		if rl.curConcurrent < rl.maxConcurrent {
			rl.curConcurrent++
			rl.sem <- struct{}{} // Add one more slot
			log.Printf("[RATE] Recovering: concurrency → %d", rl.curConcurrent)
		}
		if rl.curConcurrent >= rl.maxConcurrent {
			rl.rateLimited.Store(false)
			rl.baseDelay = 200 * time.Millisecond
		}
		atomic.StoreInt64(&rl.successCount, 0)
		rl.mu.Unlock()
	}
}

// OnRateLimit is called when a 429 is received. Reduces concurrency immediately.
func (rl *AdaptiveRateLimiter) OnRateLimit() {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	rl.rateLimited.Store(true)
	atomic.StoreInt64(&rl.successCount, 0)

	if rl.curConcurrent > 1 {
		// Drain one slot from the semaphore (reduce concurrency)
		select {
		case <-rl.sem:
			rl.curConcurrent--
			log.Printf("[RATE] 429 detected: concurrency → %d, delay → %v", rl.curConcurrent, rl.baseDelay*2)
		default:
			// Slot already taken, just increase delay
		}
	}
	// Double the inter-request delay (capped at 5s)
	rl.baseDelay *= 2
	if rl.baseDelay > 5*time.Second {
		rl.baseDelay = 5 * time.Second
	}
}
