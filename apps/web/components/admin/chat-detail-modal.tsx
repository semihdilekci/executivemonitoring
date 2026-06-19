"use client";

import { ChatMessageBubble } from "@/components/chatbot/chat-message";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { formatNumericDateTime } from "@/lib/date-format";
import type { ChatHistoryItem } from "@/types/api";

interface ChatDetailModalProps {
  item: ChatHistoryItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ChatDetailModal({ item, isOpen, onClose }: ChatDetailModalProps) {
  if (!item) return null;

  const title = `${item.user_name} · ${formatNumericDateTime(item.created_at)}`;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      className="max-w-2xl"
    >
      <div className="space-y-4">
        <ChatMessageBubble
          message={{
            id: `${item.id}-question`,
            role: "user",
            content: item.question,
          }}
        />
        <ChatMessageBubble
          message={{
            id: `${item.id}-answer`,
            role: "assistant",
            content: item.answer,
            sources: item.sources,
            tokensUsed: item.tokens_used,
            model: item.model,
          }}
          showTokenUsage
        />

        <div className="flex justify-end border-t border-gray-100 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Kapat
          </Button>
        </div>
      </div>
    </Modal>
  );
}
