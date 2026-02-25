package browser

import (
	"math"
	"math/rand"
	"time"

	"github.com/playwright-community/playwright-go"
)

// RandomDelay sleeps for a random duration between minMs and maxMs milliseconds.
func RandomDelay(minMs, maxMs int) {
	d := minMs + rand.Intn(maxMs-minMs+1)
	time.Sleep(time.Duration(d) * time.Millisecond)
}

// HumanTypeText types text character-by-character with random delays between keystrokes.
// Each keystroke has a random delay of 50-150ms, simulating a real human typist.
func HumanTypeText(page playwright.Page, selector, text string) error {
	// Click the element first to focus it (forced to bypass React overlays)
	if err := page.Locator(selector).Click(playwright.LocatorClickOptions{Force: playwright.Bool(true)}); err != nil {
		// Fallback to JS evaluate if Playwright still fails
		_, _ = page.Evaluate(`(sel) => { document.querySelector(sel)?.click() }`, selector)
	}
	// Focus input natively as well just in case
	page.Locator(selector).Focus()
	RandomDelay(100, 300) // Brief pause after focusing

	for _, ch := range text {
		if err := page.Keyboard().Press(string(ch)); err != nil {
			return err
		}
		// Random delay between 50-150ms per character (human typing speed ~40-80 WPM)
		RandomDelay(50, 150)
	}
	return nil
}

// HumanClick performs a human-like click: hesitation delay → Bézier mouse move → click.
func HumanClick(page playwright.Page, selector string) error {
	// Get element bounding box for mouse targeting
	locator := page.Locator(selector)
	box, err := locator.BoundingBox()
	if err != nil || box == nil {
		// Fallback: direct forced click if bounding box unavailable (e.g. hidden inputs)
		RandomDelay(200, 500)
		if err := page.Locator(selector).Click(playwright.LocatorClickOptions{Force: playwright.Bool(true)}); err != nil {
			_, _ = page.Evaluate(`(sel) => { document.querySelector(sel)?.click() }`, selector)
		}
		return nil
	}

	// Calculate a random point within the element (not always center — more human)
	targetX := box.X + box.Width*0.3 + rand.Float64()*box.Width*0.4
	targetY := box.Y + box.Height*0.3 + rand.Float64()*box.Height*0.4

	// Get current mouse position estimate (start from a reasonable spot)
	startX := targetX - 100 - rand.Float64()*200
	startY := targetY - 50 - rand.Float64()*100

	// Hesitation delay (200-500ms) — humans don't click instantly
	RandomDelay(200, 500)

	// Move mouse along Bézier curve
	if err := BezierMouseMove(page, startX, startY, targetX, targetY); err != nil {
		// Fallback on error
		if err := page.Locator(selector).Click(playwright.LocatorClickOptions{Force: playwright.Bool(true)}); err != nil {
			_, _ = page.Evaluate(`(sel) => { document.querySelector(sel)?.click() }`, selector)
		}
		return nil
	}

	// Small delay before click (50-150ms) — reaction time
	RandomDelay(50, 150)

	// Forced click directly on the element to bypass React overlays,
	// while still keeping the human-like mouse movement stealth above.
	if err := page.Locator(selector).Click(playwright.LocatorClickOptions{Force: playwright.Bool(true)}); err != nil {
		_, _ = page.Evaluate(`(sel) => { document.querySelector(sel)?.click() }`, selector)
	}
	return nil
}

// BezierMouseMove moves the mouse from (fromX, fromY) to (toX, toY) along a
// quadratic Bézier curve with small jitter, simulating natural hand movement.
func BezierMouseMove(page playwright.Page, fromX, fromY, toX, toY float64) error {
	steps := 15 + rand.Intn(10) // 15-24 intermediate points

	// Random control point for the Bézier curve (creates a slight arc)
	ctrlX := (fromX+toX)/2 + (rand.Float64()-0.5)*150
	ctrlY := (fromY+toY)/2 + (rand.Float64()-0.5)*100

	for i := 0; i <= steps; i++ {
		t := float64(i) / float64(steps)

		// Quadratic Bézier: B(t) = (1-t)²·P0 + 2(1-t)t·P1 + t²·P2
		x := math.Pow(1-t, 2)*fromX + 2*(1-t)*t*ctrlX + math.Pow(t, 2)*toX
		y := math.Pow(1-t, 2)*fromY + 2*(1-t)*t*ctrlY + math.Pow(t, 2)*toY

		// Add small jitter (±2px) for natural imprecision
		x += (rand.Float64() - 0.5) * 4
		y += (rand.Float64() - 0.5) * 4

		if err := page.Mouse().Move(x, y); err != nil {
			return err
		}

		// Variable speed: slower at start and end (ease-in-out)
		delay := 5 + int(15*math.Sin(t*math.Pi)) // 5-20ms between points
		time.Sleep(time.Duration(delay) * time.Millisecond)
	}
	return nil
}

// HumanScroll scrolls the page naturally with random increments and pauses.
// direction: "down" or "up". amount: total pixels to scroll.
func HumanScroll(page playwright.Page, direction string, amount int) error {
	scrolled := 0
	sign := 1.0
	if direction == "up" {
		sign = -1.0
	}

	for scrolled < amount {
		// Random scroll increment: 50-200px per step
		increment := 50 + rand.Intn(151)
		if scrolled+increment > amount {
			increment = amount - scrolled
		}

		deltaY := sign * float64(increment)
		if err := page.Mouse().Wheel(0, deltaY); err != nil {
			return err
		}
		scrolled += increment

		// Random pause between scroll steps (100-400ms)
		RandomDelay(100, 400)
	}
	return nil
}

// HumanScrollToBottom scrolls dynamically until the DOM scroll height stabilizes.
func HumanScrollToBottom(page playwright.Page) error {
	var lastHeight interface{}
	var unchangedCount int

	for {
		currentHeight, err := page.Evaluate(`document.documentElement.scrollHeight`)
		if err != nil {
			return err
		}

		if currentHeight == lastHeight {
			unchangedCount++
			if unchangedCount >= 2 {
				break // Height didn't change after 2 consecutive checks
			}
		} else {
			unchangedCount = 0
			lastHeight = currentHeight
		}

		// Scroll down by ~600-800 pixels naturally
		increment := 600 + rand.Intn(201)
		if err := HumanScroll(page, "down", increment); err != nil {
			return err
		}
		
		// Allow network/React to hydrate new content
		RandomDelay(1500, 3000)
	}
	return nil
}
