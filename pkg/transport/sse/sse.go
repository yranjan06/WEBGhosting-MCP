package sse

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"

	"github.com/metoro-io/mcp-golang/transport"
)

// SSETransport implements a server-side SSE transport for MCP
type SSETransport struct {
	ssePath     string
	messagePath string
	addr        string

	clientsMu sync.Mutex
	clients   map[chan []byte]bool

	// Handlers
	messageHandler func(ctx context.Context, message *transport.BaseJsonRpcMessage)
	errorHandler   func(error)
	closeHandler   func()
}

// NewSSEServerTransport creates a new SSE server transport
func NewSSEServerTransport(messagePath, ssePath string) *SSETransport {
	return &SSETransport{
		ssePath:     ssePath,
		messagePath: messagePath,
		clients:     make(map[chan []byte]bool),
	}
}

// Start initializes the transport. Note: For SSE, this is usually a no-op
// or starts the HTTP server if we manage it.
// However, in main.go we are using http.Handle, so this just prepares the transport.
func (t *SSETransport) Start(ctx context.Context) error {
	return nil
}

// ServeHTTP implements http.Handler for the SSE endpoint
func (t *SSETransport) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == t.ssePath {
		t.handleSSE(w, r)
		return
	}
	if r.URL.Path == t.messagePath {
		t.handleMessage(w, r)
		return
	}
	http.NotFound(w, r)
}

func (t *SSETransport) handleSSE(w http.ResponseWriter, r *http.Request) {
	// Set headers for SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Create a channel for this client
	messageChan := make(chan []byte, 10)

	// Register client
	t.clientsMu.Lock()
	t.clients[messageChan] = true
	t.clientsMu.Unlock()

	// Send initial connection message (endpoint)
	endpointEvent := fmt.Sprintf("event: endpoint\ndata: %s\n\n", t.messagePath)
	w.Write([]byte(endpointEvent))
	if f, ok := w.(http.Flusher); ok {
		f.Flush()
	}

	log.Printf("[SSE] Client connected")

	// Ensure cleanup on disconnect
	defer func() {
		t.clientsMu.Lock()
		delete(t.clients, messageChan)
		t.clientsMu.Unlock()
		close(messageChan)
		log.Printf("[SSE] Client disconnected")
	}()

	// Loop to send messages
	notify := r.Context().Done()
	for {
		select {
		case msg, ok := <-messageChan:
			if !ok {
				return
			}
			// Write message as SSE event
			// message is JSON string
			fmt.Fprintf(w, "event: message\ndata: %s\n\n", msg)
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
		case <-notify:
			return
		}
	}
}

func (t *SSETransport) handleMessage(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var msg transport.BaseJsonRpcMessage
	if err := json.Unmarshal(body, &msg); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if t.messageHandler != nil {
		// Verify strict processing (synchronous vs async)
		// Usually MCP server processes and then calls Send() to reply.
		// However, Send() puts response on SSE stream.
		// So we just return 202 Accepted here usually.
		go t.messageHandler(r.Context(), &msg)
		w.WriteHeader(http.StatusAccepted)
	} else {
		http.Error(w, "No handler registered", http.StatusInternalServerError)
	}
}

// Send sends a message to all connected SSE clients
func (t *SSETransport) Send(ctx context.Context, message *transport.BaseJsonRpcMessage) error {
	data, err := json.Marshal(message)
	if err != nil {
		return err
	}

	t.clientsMu.Lock()
	defer t.clientsMu.Unlock()

	for clientChan := range t.clients {
		select {
		case clientChan <- data:
		default:
			// client too slow, drop or buffer? Drop to avoid blocking all.
			// Ideally we use larger buffer or separate goroutine.
		}
	}
	return nil
}

func (t *SSETransport) Close() error {
	t.clientsMu.Lock()
	defer t.clientsMu.Unlock()
	for clientChan := range t.clients {
		close(clientChan)
		delete(t.clients, clientChan)
	}
	if t.closeHandler != nil {
		t.closeHandler()
	}
	return nil
}

func (t *SSETransport) SetCloseHandler(handler func()) {
	t.closeHandler = handler
}

func (t *SSETransport) SetErrorHandler(handler func(error)) {
	t.errorHandler = handler
}

func (t *SSETransport) SetMessageHandler(handler func(ctx context.Context, message *transport.BaseJsonRpcMessage)) {
	t.messageHandler = handler
}
