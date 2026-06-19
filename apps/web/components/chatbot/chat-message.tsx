"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/hooks/use-chatbot";
import { SourceCard } from "./source-card";

interface ChatMessageBubbleProps {
  message: ChatMessage;
  showTokenUsage?: boolean;
  onRetry?: () => void;
}

function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Yanıt yazılıyor">
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
    </span>
  );
}

export function ChatMessageBubble({
  message,
  showTokenUsage = false,
  onRetry,
}: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] space-y-2 sm:max-w-[75%]",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-br-md bg-navy-800 text-white"
              : "rounded-bl-md border border-gray-200 bg-white text-gray-800",
          )}
        >
          {message.status === "pending" ? (
            <TypingIndicator />
          ) : message.status === "error" ? (
            <div className="space-y-3">
              <p className="text-sm text-red-600">
                {message.errorMessage ??
                  "Yanıt üretilemedi. Lütfen tekrar deneyin."}
              </p>
              {onRetry ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={onRetry}
                >
                  Tekrar Dene
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 ? (
          <div className="space-y-2 pl-1">
            <p className="text-xs font-bold uppercase tracking-wide text-gray-500">
              Kaynak referansları
            </p>
            {message.sources.map((source) => (
              <SourceCard key={source.chunk_id} source={source} />
            ))}
          </div>
        ) : null}

        {!isUser &&
        showTokenUsage &&
        message.tokensUsed !== undefined &&
        message.status !== "pending" &&
        message.status !== "error" ? (
          <p className="pl-1 text-xs text-gray-400">
            {message.tokensUsed.toLocaleString("tr-TR")} token kullanıldı
            {message.model ? ` · ${message.model}` : ""}
          </p>
        ) : null}
      </div>
    </div>
  );
}
