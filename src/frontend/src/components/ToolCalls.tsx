import type { ToolCallView } from "../types";

export default function ToolCalls({ calls }: { calls: ToolCallView[] }) {
  if (calls.length === 0) {
    return <p className="text-xs opacity-60 italic">no tool calls</p>;
  }
  return (
    <div className="mockup-code w-full text-xs">
      {calls.map((call, index) => (
        <pre key={`${call.name}-${index}`} data-prefix={String(index + 1)}>
          <code>
            {call.name}({JSON.stringify(call.arguments)})
            {call.error !== null ? ` !! ${call.error}` : ` → ${JSON.stringify(call.result)}`}
          </code>
        </pre>
      ))}
    </div>
  );
}
