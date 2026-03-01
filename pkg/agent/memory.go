package agent

import (
	"sync"
)

// StateStore is a thread-safe key-value store for saving intermediate data
// between tool calls, particularly useful for long-running AI tasks.
type StateStore struct {
	mu   sync.RWMutex
	data map[string]interface{}
}

// NewStateStore creates a new empty state store.
func NewStateStore() *StateStore {
	return &StateStore{
		data: make(map[string]interface{}),
	}
}

// Store saves a value against a given key.
func (s *StateStore) Store(key string, value interface{}) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data[key] = value
}

// Retrieve returns the value for a given key. Returns nil if not found.
func (s *StateStore) Retrieve(key string) interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.data[key]
}

// ListKeys returns all available keys in the store.
func (s *StateStore) ListKeys() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	keys := make([]string, 0, len(s.data))
	for k := range s.data {
		keys = append(keys, k)
	}
	return keys
}

// Delete removes a key from the store.
func (s *StateStore) Delete(key string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.data, key)
}
