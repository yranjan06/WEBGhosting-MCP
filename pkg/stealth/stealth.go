package stealth

import (
	"embed"
	"encoding/json"
	"fmt"

	"github.com/playwright-community/playwright-go"
)

//go:embed js/*.js
var jsFiles embed.FS

// StealthConfig holds configuration for stealth mode
type StealthConfig struct {
	Enabled bool

	// Toggle individual scripts
	AddChromeApp             bool
	AddChromeCSI             bool
	AddChromeLoadTimes       bool
	AddChromeRuntime         bool
	AddIframeContentWindow   bool
	AddMediaCodecs           bool
	AddNavigatorHardwareConc bool
	AddNavigatorLanguages    bool
	AddNavigatorPermissions  bool
	AddNavigatorPlugins      bool
	AddNavigatorUserAgent    bool
	AddNavigatorVendor       bool
	AddNavigatorWebDriver    bool
	AddOuterDimensions       bool
	AddWebGLVendor           bool
	AddCanvasNoise           bool
	AddWebGLNoise            bool
	AddFontsSpoof            bool
	AddPermissionsSpoof      bool

	// Properties
	Vendor    string
	Renderer  string
	NavVendor string
}

// DefaultConfig returns a default configuration
func DefaultConfig() *StealthConfig {
	return &StealthConfig{
		Enabled:                  true,
		AddChromeApp:             true,
		AddChromeCSI:             true,
		AddChromeLoadTimes:       true,
		AddChromeRuntime:         true,
		AddIframeContentWindow:   true,
		AddMediaCodecs:           true,
		AddNavigatorHardwareConc: true,
		AddNavigatorLanguages:    true,
		AddNavigatorPermissions:  true,
		AddNavigatorPlugins:      true,
		AddNavigatorUserAgent:    true,
		AddNavigatorVendor:       true,
		AddNavigatorWebDriver:    true,
		AddOuterDimensions:       true,
		AddWebGLVendor:           true,
		AddCanvasNoise:           true,
		AddWebGLNoise:            true,
		AddFontsSpoof:            true,
		AddPermissionsSpoof:      true,
		Vendor:                   "Intel Inc.",
		Renderer:                 "Intel Iris OpenGL Engine",
		NavVendor:                "Google Inc.",
	}
}

// Apply applies stealth scripts to the page
func (c *StealthConfig) Apply(page playwright.Page) error {
	if !c.Enabled {
		return nil
	}

	scripts, err := c.generateScripts()
	if err != nil {
		return err
	}

	for _, script := range scripts {
		if err := page.AddInitScript(playwright.Script{
			Content: playwright.String(script),
		}); err != nil {
			return err
		}
	}

	return nil
}

func (c *StealthConfig) generateScripts() ([]string, error) {
	var scripts []string

	// 1. Generate options (simplified for now)
	opts := map[string]interface{}{
		"webgl_vendor":     c.Vendor,
		"webgl_renderer":   c.Renderer,
		"navigator_vendor": c.NavVendor,
		// TODO: Add more detailed properties as needed by the JS scripts
		"runOnInsecureOrigins": false,
	}

	optsBytes, err := json.Marshal(opts)
	if err != nil {
		return nil, err
	}

	scripts = append(scripts, fmt.Sprintf("const opts = %s", string(optsBytes)))

	// 2. Utils and Magic Arrays (Always required)
	utils, _ := jsFiles.ReadFile("js/utils.js")
	scripts = append(scripts, string(utils))

	magicArrays, _ := jsFiles.ReadFile("js/generate.magic.arrays.js")
	scripts = append(scripts, string(magicArrays))

	// 3. Conditional Scripts
	scriptMap := map[bool]string{
		c.AddChromeApp:             "js/chrome.app.js",
		c.AddChromeCSI:             "js/chrome.csi.js",
		c.AddChromeLoadTimes:       "js/chrome.load.times.js",
		c.AddChromeRuntime:         "js/chrome.runtime.js",
		c.AddIframeContentWindow:   "js/iframe.contentWindow.js",
		c.AddMediaCodecs:           "js/media.codecs.js",
		c.AddNavigatorHardwareConc: "js/navigator.hardwareConcurrency.js",
		c.AddNavigatorLanguages:    "js/navigator.languages.js",
		c.AddNavigatorPermissions:  "js/navigator.permissions.js",
		c.AddNavigatorPlugins:      "js/navigator.plugins.js",
		c.AddNavigatorUserAgent:    "js/navigator.userAgent.js",
		c.AddNavigatorVendor:       "js/navigator.vendor.js",
		c.AddNavigatorWebDriver:    "js/navigator.webdriver.js",
		c.AddOuterDimensions:       "js/window.outerdimensions.js",
		c.AddWebGLVendor:           "js/webgl.vendor.js",
		c.AddCanvasNoise:           "js/canvas.noise.js",
		c.AddWebGLNoise:            "js/webgl.noise.js",
		c.AddFontsSpoof:            "js/fonts.spoof.js",
		c.AddPermissionsSpoof:      "js/permissions.spoof.js",
	}

	for enabled, filename := range scriptMap {
		if enabled {
			content, err := jsFiles.ReadFile(filename)
			if err != nil {
				return nil, fmt.Errorf("failed to read %s: %w", filename, err)
			}
			scripts = append(scripts, string(content))
		}
	}

	return scripts, nil
}
