package plugins

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	mcp_golang "github.com/metoro-io/mcp-golang"
	"github.com/ranjanyadav/web-mcp/pkg/browser"
)

// PluginDef represents a JSON definition of a dynamic tool.
type PluginDef struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	ScriptFile  string `json:"script_file"`
}

// DynamicPluginArgs handles arguments for dynamically loaded tools.
// Right now we just pass an optional JSON payload to the script.
type DynamicPluginArgs struct {
	Args map[string]interface{} `json:"args" jsonschema:"description=Optional arguments to pass to the script"`
}

// LoadPlugins scans the extensions directory and registers them as MCP tools.
func LoadPlugins(server *mcp_golang.Server, engine *browser.Engine, extDir string) error {
	entries, err := os.ReadDir(extDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // No extensions folder, perfectly fine natively
		}
		return fmt.Errorf("failed to read extensions directory: %w", err)
	}

	count := 0
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}
		
		// Load JSON Definition
		jsonPath := filepath.Join(extDir, entry.Name())
		data, err := os.ReadFile(jsonPath)
		if err != nil {
			log.Printf("[PLUGINS] Warning: could not read %s: %v", jsonPath, err)
			continue
		}

		var def PluginDef
		if err := json.Unmarshal(data, &def); err != nil {
			log.Printf("[PLUGINS] Warning: invalid JSON in %s: %v", jsonPath, err)
			continue
		}

		// Read accompanying JS script
		scriptPath := filepath.Join(extDir, def.ScriptFile)
		scriptBytes, err := os.ReadFile(scriptPath)
		if err != nil {
			log.Printf("[PLUGINS] Warning: could not read script %s for tool '%s': %v", scriptPath, def.Name, err)
			continue
		}
		scriptContent := string(scriptBytes)

		// Create closure for the tool
		pluginName := def.Name
		pluginDesc := def.Description + " [Dynamic Plugin]"

		err = server.RegisterTool(pluginName, pluginDesc, func(args DynamicPluginArgs) (*mcp_golang.ToolResponse, error) {
			log.Printf("  [PLUGIN] Executing dynamic tool: %s", pluginName)
			
			// If arguments were passed, inject them into the script context
			argsJSON := "{}"
			if len(args.Args) > 0 {
				b, _ := json.Marshal(args.Args)
				argsJSON = string(b)
			}

			// Wrap the user script so it receives the arguments
			wrappedScript := fmt.Sprintf(`
				(() => {
					const args = %s;
					const pluginExecution = %s;
					if (typeof pluginExecution === 'function') {
						return pluginExecution(args);
					}
					return pluginExecution;
				})()
			`, argsJSON, scriptContent)

			result, err := engine.ExecuteScript(wrappedScript)
			if err != nil {
				return nil, fmt.Errorf("plugin execution failed: %w", err)
			}
			
			// Try to pretty print if it's JSON String
			var obj interface{}
			if json.Unmarshal([]byte(result), &obj) == nil {
				if pretty, err := json.MarshalIndent(obj, "", "  "); err == nil {
					result = string(pretty)
				}
			} else if strings.HasPrefix(result, "\"") && strings.HasSuffix(result, "\"") {
				// unescape quotes
				result = strings.Trim(result, "\"")
				result = strings.ReplaceAll(result, "\\\"", "\"")
			}

			return mcp_golang.NewToolResponse(mcp_golang.NewTextContent(result)), nil
		})

		if err != nil {
			log.Printf("[PLUGINS] Warning: could not register tool '%s': %v", pluginName, err)
			continue
		}
		
		count++
		log.Printf("[PLUGINS] Successfully loaded tool '%s'", pluginName)
	}

	if count > 0 {
		log.Printf("[PLUGINS] Finished loading %d dynamic extensions", count)
	}
	return nil
}
