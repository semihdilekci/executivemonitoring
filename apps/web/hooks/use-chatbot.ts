"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { ChatAskRequest, ChatAskResponse, ChatSource } from "@/types/api";
import { isApiError } from "@/types/api";

export type ChatMessageRole = "user" | "assistant";

export type ChatMessageStatus = "pending" | "error";

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  sources?: ChatSource[];
  tokensUsed?: number;
  model?: string;
  status?: ChatMessageStatus;
  errorMessage?: string;
}

/** null = henüz test edilmedi; false = backend extra=forbid veya alan desteklemiyor. */
let chatDigestContextApiSupported: boolean | null = null;

async function askChatbot(
  question: string,
  digestId?: string | null,
): Promise<ChatAskResponse> {
  const baseBody: ChatAskRequest = { question };

  if (!digestId || chatDigestContextApiSupported === false) {
    const response = await apiClient.post<ChatAskResponse>("/chat", baseBody);
    return response.data;
  }

  const bodyWithContext: ChatAskRequest = { ...baseBody, digest_id: digestId };

  try {
    const response = await apiClient.post<ChatAskResponse>(
      "/chat",
      bodyWithContext,
    );
    chatDigestContextApiSupported = true;
    return response.data;
  } catch (error) {
    if (
      chatDigestContextApiSupported === null &&
      isApiError(error) &&
      (error.statusCode === 422 || error.code === "VALIDATION_ERROR")
    ) {
      chatDigestContextApiSupported = false;
      const fallback = await apiClient.post<ChatAskResponse>("/chat", baseBody);
      return fallback.data;
    }
    throw error;
  }
}

export function useChatbot(options?: { digestId?: string | null }) {
  const digestId = options?.digestId ?? null;
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);
  const [lastFailedQuestion, setLastFailedQuestion] = useState<string | null>(
    null,
  );

  const askMutation = useMutation({
    mutationFn: (question: string) => askChatbot(question, digestId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory.all });
    },
  });

  const sendQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || askMutation.isPending) {
        return;
      }

      setRateLimitMessage(null);
      setLastFailedQuestion(null);

      const userMessageId = crypto.randomUUID();
      const assistantMessageId = crypto.randomUUID();

      setMessages((current) => [
        ...current,
        { id: userMessageId, role: "user", content: trimmed },
        {
          id: assistantMessageId,
          role: "assistant",
          content: "",
          status: "pending",
        },
      ]);

      try {
        const response = await askMutation.mutateAsync(trimmed);
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantMessageId
              ? {
                  id: assistantMessageId,
                  role: "assistant",
                  content: response.answer,
                  sources: response.sources,
                  tokensUsed: response.tokens_used,
                  model: response.model,
                }
              : message,
          ),
        );
      } catch (error) {
        if (isApiError(error) && error.statusCode === 429) {
          setRateLimitMessage(
            "Çok fazla soru gönderildi. Lütfen biraz bekleyin.",
          );
          setLastFailedQuestion(trimmed);
          setMessages((current) =>
            current.filter((message) => message.id !== assistantMessageId),
          );
          return;
        }

        const errorMessage = isApiError(error)
          ? error.message
          : "Yanıt üretilemedi. Lütfen tekrar deneyin.";

        setLastFailedQuestion(trimmed);
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  content: "",
                  status: "error",
                  errorMessage,
                }
              : message,
          ),
        );
      }
    },
    [askMutation],
  );

  const retryLastQuestion = useCallback(() => {
    if (!lastFailedQuestion) return;
    void sendQuestion(lastFailedQuestion);
  }, [lastFailedQuestion, sendQuestion]);

  const dismissRateLimit = useCallback(() => {
    setRateLimitMessage(null);
  }, []);

  return {
    messages,
    sendQuestion,
    retryLastQuestion,
    isPending: askMutation.isPending,
    rateLimitMessage,
    dismissRateLimit,
    lastFailedQuestion,
  };
}
