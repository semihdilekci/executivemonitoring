"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function ChatbotShortcut() {
  const router = useRouter();
  const [question, setQuestion] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    const params = new URLSearchParams({ q: trimmed });
    router.push(`/chatbot?${params.toString()}`);
  }

  return (
    <Card padding="lg" className="border-gray-100">
      <div className="flex items-start gap-3">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-navy-100 text-lg"
          aria-hidden
        >
          🤖
        </span>
        <form className="flex-1 space-y-3" onSubmit={handleSubmit}>
          <div>
            <label
              htmlFor="chatbot-shortcut-input"
              className="text-sm font-semibold text-navy-800"
            >
              AI Chatbot&apos;a sor
            </label>
            <p className="mt-1 text-xs text-gray-500">
              Sorunuzu yazın; chatbot ekranında devam edebilirsiniz.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              id="chatbot-shortcut-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Örn: Bu hafta FMCG sektöründe ne oldu?"
              aria-label="Chatbot sorusu"
            />
            <Button type="submit" className="shrink-0">
              Gönder
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}
