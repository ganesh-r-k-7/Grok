"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { formatDistanceToNow } from "date-fns";
import { aiApi, Conversation, Message, ConversationRole, StreamChunk } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { marked } from "marked";

interface ConversationListProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  isLoading: boolean;
}

export function ConversationList({
  conversations,
  activeConversationId,
  onSelect,
  onNew,
  onDelete,
  isLoading,
}: ConversationListProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <Button variant="ghost" className="w-full justify-start" disabled>
            <svg className="mr-2 w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="truncate">Loading...</span>
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse bg-slate-200 dark:bg-slate-700 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 border-b border-slate-200 dark:border-slate-700">
        <Button
          variant="primary"
          className="w-full justify-start gap-2"
          onClick={onNew}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Chat</span>
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {conversations.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            <svg className="mx-auto w-12 h-12 mb-3 text-slate-300 dark:text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h4M8 16h4m-4-8h4m-4 0v12" />
            </svg>
            <p className="text-sm">No conversations yet</p>
            <p className="text-xs mt-1">Start a new conversation</p>
          </div>
        ) : (
          conversations.map((conversation) => (
            <div
              key={conversation.id}
              onMouseEnter={() => setHoveredId(conversation.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <button
                onClick={() => onSelect(conversation.id)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors",
                  activeConversationId === conversation.id
                    ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{conversation.title}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
                      {formatDistanceToNow(new Date(conversation.updated_at), { addSuffix: true })}
                    </p>
                  </div>
                  {hoveredId === conversation.id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(conversation.id);
                      }}
                      className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                      aria-label="Delete conversation"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v12m-6 0h12a2 2 0 002-2V9a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </button>
                  )}
                </div>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

interface StreamingMessage {
  id: string;
  role: ConversationRole;
  content: string;
  isStreaming: boolean;
  toolCalls?: Array<{
    id: string;
    name: string;
    arguments: string;
  }>;
  toolResults?: Array<any>;
  error?: string;
  created_at?: string;
}

type DisplayMessage = Message | StreamingMessage;

function isStreamingMessage(msg: DisplayMessage): msg is StreamingMessage {
  return "isStreaming" in msg;
}

interface MessageListProps {
  messages: (Message | StreamingMessage)[];
  isLoading: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center p-8">
          <svg className="mx-auto w-16 h-16 text-slate-300 dark:text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h4M8 16h4m-4-8h4m-4 0v12" />
          </svg>
          <p className="text-slate-500 dark:text-slate-400">No messages yet</p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Start a conversation with GROK</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
}

function renderMarkdown(content: string) {
  return { __html: marked.parse(content, { async: false }) as string };
}

function MessageBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isTool = message.role === "tool";
  const isStreaming = isStreamingMessage(message) && message.isStreaming;
  const toolCalls = isStreamingMessage(message) ? message.toolCalls : undefined;
  const toolResults = isStreamingMessage(message) ? message.toolResults : undefined;
  const error = isStreamingMessage(message) ? message.error : undefined;

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
          {isTool ? (
            <svg className="w-5 h-5 text-primary-700 dark:text-primary-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-primary-700 dark:text-primary-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          )}
        </div>
      )}

      <div className={cn("flex-1 min-w-0", isUser && "text-right")}>
        <div className={cn(
          "inline-block max-w-[80%] px-4 py-2.5 rounded-2xl text-sm",
          isUser
            ? "bg-primary-600 text-white rounded-tr-none"
            : isTool
            ? "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200 rounded-tl-none"
            : "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100 rounded-tl-none"
        )}>
          {isAssistant && !isUser ? (
            <div dangerouslySetInnerHTML={renderMarkdown(message.content)} />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
          {isStreaming && <span className="animate-pulse">▌</span>}
        </div>

        {toolCalls && toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {toolCalls.map((tc) => (
              <ToolCallBadge key={tc.id} name={tc.name} arguments={tc.arguments} />
            ))}
          </div>
        )}

        {toolResults && toolResults.length > 0 && (
          <div className="mt-2 space-y-1">
            {toolResults.map((tr: any, idx: number) => (
              <ToolResultBadge key={idx} result={tr} />
            ))}
          </div>
        )}

        {error && (
          <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-xs rounded">
            {error}
          </div>
        )}

        <p className={cn("mt-1 text-xs", isUser ? "text-slate-400" : "text-slate-500 dark:text-slate-400")}>
          {"created_at" in message && message.created_at ? formatDistanceToNow(new Date(message.created_at), { addSuffix: true }) : "Just now"}
        </p>
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
          <svg className="w-5 h-5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h18a7 7 0 00-7-7z" />
          </svg>
        </div>
      )}
    </div>
  );
}

function ToolCallBadge({ name, arguments: args }: { name: string; arguments: string }) {
  let displayArgs = "";
  try {
    const parsed = JSON.parse(args);
    displayArgs = Object.entries(parsed).map(([k, v]) => `${k}: ${String(v)}`).join(", ");
  } catch {
    displayArgs = args;
  }

  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs rounded-full">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <span>{name}</span>
      {displayArgs && <span className="opacity-70">{displayArgs}</span>}
    </div>
  );
}

function ToolResultBadge({ result }: { result: any }) {
  const isSuccess = result.success !== false;

  if (result.task) {
    return (
      <div className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-full",
        isSuccess ? "bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300" : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300"
      )}>
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isSuccess ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          )}
        </svg>
        <span>Task {isSuccess ? "created" : "failed"}: {result.task.title}</span>
      </div>
    );
  }

  if (result.tasks) {
    return (
      <div className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-full",
        isSuccess ? "bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300" : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300"
      )}>
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span>{result.total} task(s) found</span>
      </div>
    );
  }

  if (result.message) {
    return (
      <div className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-full",
        isSuccess ? "bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300" : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300"
      )}>
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isSuccess ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          )}
        </svg>
        <span>{result.message}</span>
      </div>
    );
  }

  return null;
}

interface ComposerProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function Composer({ onSend, onStop, isLoading, disabled }: ComposerProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (message.trim() && !isLoading) {
        onSend(message.trim());
        setMessage("");
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
        }
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t border-slate-200 dark:border-slate-700">
      <div className="flex gap-2">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={isLoading ? "Generating response..." : "Message GROK... (Shift+Enter for new line)"}
          disabled={isLoading || disabled}
          rows={1}
          className="flex-1 resize-none p-3 pr-10 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50"
          style={{ minHeight: "44px", maxHeight: "200px" }}
        />
        {isLoading ? (
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={onStop}
            className="flex-shrink-0 h-11"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
          </Button>
        ) : (
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={!message.trim() || disabled}
            className="flex-shrink-0 h-11"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </Button>
        )}
      </div>
      <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 text-center">
        Press Enter to send, Shift+Enter for new line
      </p>
    </form>
  );
}

export function ChatInterface() {
  const queryClient = useQueryClient();
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<(Message | StreamingMessage)[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch conversations
  const { data: conversationsData, isLoading: conversationsLoading } = useQuery({
    queryKey: ["ai-conversations"],
    queryFn: () => aiApi.listConversations({ page_size: 50 }),
  });

  const conversations = conversationsData?.conversations || [];

  // Fetch messages for active conversation
  const { data: messagesData, isLoading: messagesLoading, refetch: refetchMessages } = useQuery({
    queryKey: ["ai-conversation-messages", activeConversationId],
    queryFn: () => aiApi.getMessages(activeConversationId!),
    enabled: !!activeConversationId,
  });

  const allMessages = messagesData?.messages || [];

  const handleSend = useCallback(async (message: string) => {
    if (!activeConversationId && !message.trim()) return;

    setIsStreaming(true);
    setStreamError(null);

    // Optimistically add user message
    const tempUserMessage: StreamingMessage = {
      id: `temp-user-${Date.now()}`,
      role: "user",
      content: message,
      isStreaming: false,
    };
    setMessages((prev) => [...prev, tempUserMessage]);

    // Create placeholder for streaming assistant message
    const assistantMessageId = `temp-assistant-${Date.now()}`;
    const assistantMessage: StreamingMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      isStreaming: true,
      toolCalls: [],
      toolResults: [],
    };
    setMessages((prev) => [...prev, assistantMessage]);

    abortControllerRef.current = new AbortController();

    try {
      const response = await aiApi.chatStream({
        message,
        conversation_id: activeConversationId || undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      if (!reader) throw new Error("No response body");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;

            try {
              const chunk: StreamChunk = JSON.parse(data);

              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id !== assistantMessageId) return msg;
                  if (!isStreamingMessage(msg)) return msg;

                  const updated: StreamingMessage = { ...msg };

                  if (chunk.type === "content" && chunk.content) {
                    updated.content += chunk.content;
                  } else if (chunk.type === "tool_call" && chunk.tool_call) {
                    updated.toolCalls = [
                      ...(updated.toolCalls || []),
                      {
                        id: chunk.tool_call.id,
                        name: chunk.tool_call.function.name,
                        arguments: chunk.tool_call.function.arguments,
                      },
                    ];
                  } else if (chunk.type === "tool_result" && chunk.tool_result) {
                    updated.toolResults = [
                      ...(updated.toolResults || []),
                      chunk.tool_result,
                    ];
                  } else if (chunk.type === "error" && chunk.error) {
                    updated.error = chunk.error;
                    updated.isStreaming = false;
                  } else if (chunk.type === "done") {
                    updated.isStreaming = false;
                    if (chunk.conversation_id) {
                      updated.id = chunk.conversation_id;
                    }
                  }

                  return updated;
                })
              );
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }

      // After streaming completes, invalidate queries to refresh
      queryClient.invalidateQueries({ queryKey: ["ai-conversation-messages", activeConversationId || ""] });
      queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to send message";
      setStreamError(errorMessage);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, error: errorMessage, isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }, [activeConversationId, queryClient]);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsStreaming(false);
    // Mark the streaming message as stopped
    setMessages((prev) =>
      prev.map((msg) =>
        isStreamingMessage(msg) && msg.isStreaming ? { ...msg, isStreaming: false, error: "Stopped by user" } : msg
      )
    );
  }, []);

  const handleRetry = useCallback((messageId: string) => {
    const message = messages.find((m) => m.id === messageId);
    if (message && message.role === "user") {
      // Remove the failed assistant response and retry
      setMessages((prev) => prev.filter((m) => m.id !== messageId && m.role !== "assistant"));
      handleSend(message.content);
    }
  }, [messages, handleSend]);

  const handleNewConversation = useCallback(async () => {
    try {
      const newConversation = await aiApi.createConversation({ title: "New Conversation" });
      setActiveConversationId(newConversation.id);
      setMessages([]);
      setStreamError(null);
      queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
    } catch (error) {
      console.error("Failed to create conversation:", error);
      setStreamError("Failed to create new conversation");
    }
  }, [queryClient]);

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    setStreamError(null);
  };

  const handleDeleteConversation = (id: string) => {
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
    }
    queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
  };

  // Merge fetched messages with local streaming messages
  const displayMessages = [...allMessages, ...messages.filter(m => m.id.startsWith("temp-"))];

  return (
    <div className="flex h-full w-full min-w-0 bg-slate-50 dark:bg-slate-950">
      {/* Sidebar */}
      <aside className={cn(
        "w-80 flex-shrink-0 flex flex-col border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 transition-all duration-200 lg:w-80",
        isSidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <ConversationList
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          isLoading={conversationsLoading}
        />
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header with mobile sidebar toggle */}
        <header className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 lg:hidden">
          <Button variant="ghost" size="sm" onClick={() => setIsSidebarOpen(!isSidebarOpen)} aria-label="Toggle conversations">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </Button>
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">GROK</h1>
          <div className="w-10" />
        </header>
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <MessageList
            messages={displayMessages}
            isLoading={messagesLoading && messages.length === 0}
          />
          <Composer
            onSend={handleSend}
            onStop={handleStop}
            isLoading={isStreaming}
            disabled={!activeConversationId}
          />
        </div>
      </main>
    </div>
  );
}

export default ChatInterface;