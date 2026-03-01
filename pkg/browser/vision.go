package browser

import (
	"encoding/base64"
	"fmt"
	"log"

	"github.com/playwright-community/playwright-go"
)

// GetLabeledScreenshot injects CSS/JS to draw bounding boxes with labels over
// interactive elements, takes a screenshot, and returns the base64 encoded image
// along with a map of labels to their CSS selectors.
func (e *Engine) GetLabeledScreenshot() (string, map[string]string, error) {
	if err := e.EnsureInitialized(); err != nil {
		return "", nil, err
	}

	page := e.activePage()
	if page == nil {
		return "", nil, fmt.Errorf("no active tab")
	}

	log.Println("[VISION] Injecting bounding boxes...")

	// 1. Inject the JavaScript to draw the boxes and gather the map
	script := `() => {
		// Clean up any existing boxes first
		const existing = document.querySelectorAll('.openclaw-vision-box');
		existing.forEach(el => el.remove());

		const interactibles = document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"]');
		const labelMap = {};
		let counter = 1;

		interactibles.forEach(el => {
			const rect = el.getBoundingClientRect();
			// Only box visible elements
			if (rect.width === 0 || rect.height === 0 || rect.top < 0 || rect.left < 0) return;

			// Generate a simple CSS selector or xpath to uniquely identify it later if needed.
			// For simplicity we just assign an ID if one doesn't exist to make it targetable.
			let targetId = el.id;
			if (!targetId) {
				targetId = 'openclaw-vlm-' + counter;
				el.id = targetId;
			}
			const selector = '#' + targetId;

			const label = 'e' + counter++;
			labelMap[label] = selector;

			const box = document.createElement('div');
			box.className = 'openclaw-vision-box';
			box.style.position = 'absolute';
			box.style.left = (window.scrollX + rect.left) + 'px';
			box.style.top = (window.scrollY + rect.top) + 'px';
			box.style.width = rect.width + 'px';
			box.style.height = rect.height + 'px';
			box.style.border = '2px solid red';
			box.style.boxSizing = 'border-box';
			box.style.zIndex = '999999';
			box.style.pointerEvents = 'none';

			const tag = document.createElement('div');
			tag.className = 'openclaw-vision-box'; // so it gets cleaned up
			tag.textContent = label;
			tag.style.position = 'absolute';
			tag.style.left = (window.scrollX + rect.left) + 'px';
			tag.style.top = (window.scrollY + Math.max(0, rect.top - 20)) + 'px';
			tag.style.background = 'red';
			tag.style.color = 'white';
			tag.style.fontSize = '12px';
			tag.style.fontWeight = 'bold';
			tag.style.padding = '2px 4px';
			tag.style.zIndex = '1000000';
			tag.style.pointerEvents = 'none';

			document.body.appendChild(box);
			document.body.appendChild(tag);
		});

		return labelMap;
	}`

	result, err := page.Evaluate(script)
	if err != nil {
		return "", nil, fmt.Errorf("failed to inject vision boxes: %w", err)
	}

	labelMap := make(map[string]string)
	if resultMap, ok := result.(map[string]interface{}); ok {
		for k, v := range resultMap {
			if strVal, ok := v.(string); ok {
				labelMap[k] = strVal
			}
		}
	}

	log.Printf("[VISION] Drawn boxes for %d elements. Taking screenshot...", len(labelMap))

	// 2. Take the screenshot
	screenshotBytes, err := page.Screenshot(playwright.PageScreenshotOptions{
		Type:     playwright.ScreenshotTypeJpeg,
		Quality:  playwright.Int(80),
		FullPage: playwright.Bool(false), // Only visible viewport to save tokens usually
	})

	if err != nil {
		return "", nil, fmt.Errorf("failed to take screenshot: %w", err)
	}

	// 3. Clean up the injected elements
	cleanupScript := `() => {
		const existing = document.querySelectorAll('.openclaw-vision-box');
		existing.forEach(el => el.remove());
	}`
	_, _ = page.Evaluate(cleanupScript)

	base64encoded := base64.StdEncoding.EncodeToString(screenshotBytes)
	return base64encoded, labelMap, nil
}
