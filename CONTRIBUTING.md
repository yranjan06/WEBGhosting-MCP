# Contributing to Go-WebMCP

First off — thank you for considering contributing! Go-WebMCP is built with ❤️ for the AI community, and every contribution makes it better for everyone.

## Ways to Contribute

### Report Bugs
Open an issue with:
- Go version (`go version`)
- OS and architecture
- Steps to reproduce
- Expected vs actual behavior

### Suggest Features
Open an issue with the `enhancement` label describing:
- The use case
- Proposed behavior
- Any alternatives you've considered

### Submit Code

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch**: `git checkout -b feature/my-feature`
4. **Make your changes** (see guidelines below)
5. **Test**: `make build` must pass
6. **Commit**: Use clear, descriptive commit messages
7. **Push**: `git push origin feature/my-feature`
8. **Open a Pull Request**

## Adding New Stealth Scripts

One of the easiest ways to contribute! To add a new browser fingerprint bypass:

1. Create your JavaScript file in `pkg/stealth/js/your_script.js`
2. Add a toggle field in `StealthConfig` struct (`pkg/stealth/stealth.go`):
   ```go
   AddYourScript bool
   ```
3. Set the default to `true` in `DefaultConfig()`
4. Add the mapping in `generateScripts()`:
   ```go
   c.AddYourScript: "js/your_script.js",
   ```
5. Done — it will be auto-embedded and injected via `//go:embed js/*.js`

## Adding New MCP Tools

1. Define your arg struct in `cmd/server/tools.go`:
   ```go
   type MyToolArgs struct {
       Param string `json:"param" jsonschema:"required,description=What this param does"`
   }
   ```
2. Register the handler inside `RegisterAllTools()`:
   ```go
   must(server.RegisterTool("my_tool", "Description", func(args MyToolArgs) (*mcp_golang.ToolResponse, error) {
       // Your logic here
       return mcp_golang.NewToolResponse(mcp_golang.NewTextContent("result")), nil
   }))
   ```

## Code Style

- Follow standard Go conventions (`gofmt`, `go vet`)
- Add comments for exported functions
- Keep functions focused — one responsibility per function
- Use meaningful variable names

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
