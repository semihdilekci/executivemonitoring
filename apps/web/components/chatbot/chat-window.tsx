"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { CHATBOT_EXAMPLE_QUESTIONS } from "@/lib/constants";
import { useAuth } from "@/hooks/use-auth";
import { useChatbot } from "@/hooks/use-chatbot";
import { ChatInput } from "./chat-input";
import { ChatMessageBubble } from "./chat-message";

interface ChatWindowProps {
  initialQuestion?: string | null;
  digestId?: string | null;
}

export function ChatWindow({ initialQuestion, digestId }: ChatWindowProps) {
  const { isAdmin } = useAuth();
  const {
    messages,
    sendQuestion,
    retryLastQuestion,
    isPending,
    rateLimitMessage,
    dismissRateLimit,
    lastFailedQuestion,
  } = useChatbot({ digestId });

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const initialQuestionSentRef = useRef(false);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages, isPending]);

  useEffect(() => {
    if (!initialQuestion || initialQuestionSentRef.current) return;
    initialQuestionSentRef.current = true;
    void sendQuestion(initialQuestion);
  }, [initialQuestion, sendQuestion]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex min-h-[calc(100dvh-10rem)] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {rateLimitMessage ? (
        <div
          className="flex items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          role="alert"
        >
          <span>{rateLimitMessage}</span>
          <div className="flex shrink-0 items-center gap-2">
            {lastFailedQuestion ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => {
                  dismissRateLimit();
                  void sendQuestion(lastFailedQuestion);
                }}
              >
                Tekrar Dene
              </Button>
            ) : null}
            <button
              type="button"
              onClick={dismissRateLimit}
              className="rounded-md px-2 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-100"
              aria-label="Uyarıyı kapat"
            >
              Kapat
            </button>
          </div>
        </div>
      ) : null}

      {digestId ? (
        <div className="border-b border-gold-100 bg-gold-50 px-4 py-3 text-sm text-navy-800">
          Bu bülten hakkında sorular sorabilirsiniz. Yanıtlar platform
          veritabanındaki tüm içerik üzerinden üretilir.
        </div>
      ) : null}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 py-6"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Sohbet mesajları"
      >
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center">
            <span
              className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-navy-800 to-navy-600 text-2xl text-gold-400 shadow-md"
              aria-hidden
            >
              ✦
            </span>
            <h1 className="text-lg font-bold text-navy-800">YGIP AI Asistan</h1>
            <p className="mt-2 max-w-md text-sm text-gray-500">
              Platform veritabanındaki tüm içerik üzerinde soru
              sorabilirsiniz.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {CHATBOT_EXAMPLE_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  disabled={isPending}
                  onClick={() => {
                    void sendQuestion(question);
                  }}
                  className="rounded-full border border-gray-200 bg-gray-50 px-4 py-2 text-sm font-medium text-navy-800 transition-colors hover:border-navy-200 hover:bg-navy-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                showTokenUsage={isAdmin}
                onRetry={
                  message.status === "error" ? retryLastQuestion : undefined
                }
              />
            ))}
          </div>
        )}
      </div>

      <ChatInput onSend={sendQuestion} disabled={isPending} />
    </div>
  );
}
