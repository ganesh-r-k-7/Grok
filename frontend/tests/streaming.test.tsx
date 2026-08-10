import { describe, it, expect, vi } from "vitest";

// Test SSE parsing logic extracted from ChatInterface
function parseSSEStream(stream: string): Array<{ type: string; content?: string; tool_call?: any; tool_result?: any; error?: string; usage?: any; conversation_id?: string }> {
  const lines = stream.split("\n");
  const events: Array<{ type: string; content?: string; tool_call?: any; tool_result?: any; error?: string; usage?: any; conversation_id?: string }> = [];
  
  let buffer = "";
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = line.slice(6);
      if (data === "[DONE]") continue;
      
      try {
        const chunk = JSON.parse(data);
        events.push(chunk);
      } catch (e) {
        // Ignore parse errors
      }
    }
  }
  
  return events;
}

describe("SSE Stream Parsing", () => {
  it("parses basic content chunks", () => {
    const stream = `
data: {"type": "content", "content": "Hello"}
data: {"type": "content", "content": " world"}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ type: "content", content: "Hello" });
    expect(events[1]).toEqual({ type: "content", content: " world" });
    expect(events[2]).toEqual({ type: "done", conversation_id: "test-conv-id" });
  });

  it("parses tool call chunks", () => {
    const stream = `
data: {"type": "tool_call", "tool_call": {"id": "call_1", "function": {"name": "create_task", "arguments": "{\\"title\\": \\"Test Task\\"}"}}}
data: {"type": "tool_result", "tool_result": {"success": true, "task": {"title": "Test Task", "status": "todo"}}}
data: {"type": "content", "content": "Task created!"}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(4);
    expect(events[0].type).toBe("tool_call");
    expect(events[0].tool_call).toBeDefined();
    expect(events[0].tool_call.function.name).toBe("create_task");
    
    expect(events[1].type).toBe("tool_result");
    expect(events[1].tool_result).toBeDefined();
    expect(events[1].tool_result.success).toBe(true);
    
    expect(events[2].type).toBe("content");
    expect(events[2].content).toBe("Task created!");
    
    expect(events[3].type).toBe("done");
    expect(events[3].conversation_id).toBe("test-conv-id");
  });

  it("parses error chunks", () => {
    const stream = `
data: {"type": "error", "error": "Provider is down"}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "error", error: "Provider is down" });
    expect(events[1]).toEqual({ type: "done", conversation_id: "test-conv-id" });
  });

  it("parses usage information", () => {
    const stream = `
data: {"type": "content", "content": "Response"}
data: {"type": "done", "conversation_id": "test-conv-id", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(2);
    expect(events[1].usage).toEqual({
      prompt_tokens: 10,
      completion_tokens: 20,
      total_tokens: 30,
    });
  });

  it("ignores invalid JSON lines", () => {
    const stream = `
data: {"type": "content", "content": "Valid"}
data: not valid json
data: {"type": "content", "content": "Also valid"}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(2);
    expect(events[0].content).toBe("Valid");
    expect(events[1].content).toBe("Also valid");
  });

  it("ignores [DONE] marker", () => {
    const stream = `
data: {"type": "content", "content": "Hello"}
data: [DONE]
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    
    expect(events).toHaveLength(2);
    expect(events[0].content).toBe("Hello");
    expect(events[1].type).toBe("done");
  });
});

describe("Streaming Message Accumulation", () => {
  it("accumulates content chunks correctly", () => {
    const stream = `
data: {"type": "content", "content": "Hel"}
data: {"type": "content", "content": "lo"}
data: {"type": "content", "content": " world"}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    let fullContent = "";
    
    for (const event of events) {
      if (event.type === "content" && event.content) {
        fullContent += event.content;
      }
    }
    
    expect(fullContent).toBe("Hello world");
  });

  it("collects tool calls and results", () => {
    const stream = `
data: {"type": "tool_call", "tool_call": {"id": "call_1", "function": {"name": "create_task", "arguments": "{\\"title\\": \\"Task 1\\"}"}}}
data: {"type": "tool_call", "tool_call": {"id": "call_2", "function": {"name": "list_tasks", "arguments": "{}"}}}
data: {"type": "tool_result", "tool_result": {"success": true, "task": {"title": "Task 1"}}}
data: {"type": "tool_result", "tool_result": {"success": true, "tasks": [{"title": "Task 1"}, {"title": "Task 2"}]}}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    const toolCalls: any[] = [];
    const toolResults: any[] = [];
    
    for (const event of events) {
      if (event.type === "tool_call" && event.tool_call) {
        toolCalls.push(event.tool_call);
      } else if (event.type === "tool_result" && event.tool_result) {
        toolResults.push(event.tool_result);
      }
    }
    
    expect(toolCalls).toHaveLength(2);
    expect(toolCalls[0].function.name).toBe("create_task");
    expect(toolCalls[1].function.name).toBe("list_tasks");
    
    expect(toolResults).toHaveLength(2);
    expect(toolResults[0].success).toBe(true);
    expect(toolResults[1].success).toBe(true);
  });

  it("handles multiple done events (provider + API)", () => {
    const stream = `
data: {"type": "content", "content": "Hello"}
data: {"type": "done", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    const doneEvents = events.filter(e => e.type === "done");
    
    expect(doneEvents).toHaveLength(2);
    // First done from provider has usage
    expect(doneEvents[0].usage).toBeDefined();
    // Second done from API has conversation_id
    expect(doneEvents[1].conversation_id).toBe("test-conv-id");
  });
});

describe("Error Handling in Streaming", () => {
  it("detects error events", () => {
    const stream = `
data: {"type": "content", "content": "Partial"}
data: {"type": "error", "error": "Connection lost"}
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    const errorEvent = events.find(e => e.type === "error");
    
    expect(errorEvent).toBeDefined();
    expect(errorEvent?.error).toBe("Connection lost");
  });

  it("handles empty stream", () => {
    const stream = "";
    const events = parseSSEStream(stream);
    expect(events).toHaveLength(0);
  });

  it("handles stream with only done event", () => {
    const stream = `
data: {"type": "done", "conversation_id": "test-conv-id"}
`;
    
    const events = parseSSEStream(stream);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("done");
  });
});