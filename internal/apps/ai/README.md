# `internal/apps/ai`

## Responsibility

The Go AI package owns the authenticated AI API surface under `/api/v1/ai/`: provider settings with masked keys, usage accounting, conversations, message history, chat-related state, and upload processing-status reads.

## Separation from indexing

Document extraction and chunk creation run in `services/ai-indexer`, not in the Go HTTP handler. The Go AI package reads processing-job status and serves AI-facing domain data. The indexer updates `ai_aiprocessingjob` and `ai_documentchunk` using the existing schema.

## Security and usage

API keys are masked in responses. Usage updates must be atomic enough to enforce daily limits and should use PostgreSQL as the durable authority. Conversation and message queries must scope by authenticated user and class access. Provider calls should use bounded timeouts and must not log prompts, keys, or private document text.
